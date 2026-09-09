"""Infinite streaming chunk world: lazy generation, biomes, seam-safe borders.

Chunks are `chunk_size`-square tile grids keyed (cx, cy) in a dict, generated
lazily (preload radius around the agent via `ensure_loaded`; `tile_at`
generates as a backstop) and never discarded — the world persists in RAM.
Generation is a pure function of (world_seed, cx, cy, config): same inputs,
identical chunk, negative coordinates included, no cross-chunk state.

Seams (the scheme, exactly):
- Every generator keeps the chunk border solid WALL; the ONLY border openings
  are the seam corridors drilled by the chunk pipeline.
- Each of the 4 shared borders is canonically owned by one chunk: the border
  east of (cx, cy) is ("V", cx, cy); the border south of it is ("H", cx, cy).
  Both neighbours hash the SAME canonical id, so the crossing offset
  j = hash(world_seed, kind, owner...) % (2*seam_jitter + 1) - seam_jitter
  agrees on both sides with no communication.
- A chunk drills one L-shaped corridor per edge: a leg along the center
  row/column from the chunk center, then a leg on the jittered line that
  crosses the border. For a "V" border both half-corridors run along the same
  global row (chunk-center row + j); for an "H" border, the same global
  column. Each half ends on its own border tile at the crossing — adjacent
  tiles, both FLOOR: that pair IS the "edge midpoint tile, FLOOR in both
  chunks", and the half-corridors connect through it.
- After seams, an interior-connectivity pass floods from the chunk center
  (agent movement rules: 8-dir, no corner cutting) and drills any unreachable
  FLOOR pocket into the main cavity. Every step of the pipeline only adds
  FLOOR, so reachability is monotone; with every chunk center tied to its
  neighbours by seam corridors, the whole generated world is walkable from
  spawn.

Biomes by distance from world origin (Euclidean, measured at the chunk-center
tile, documented choice): noised distance < band_bsp_max -> per-chunk BSP
rooms+corridors (gen_bsp); < band_cavern_min -> CA caves (gen_cave); else ->
CA caverns with liquid pools (gen_cavern). The distance is blurred by hashed
per-tile noise of amplitude band_blend_noise evaluated at the chunk-center
tile, so band-edge chunks pick their generator per-noise and the boundaries
dither instead of forming hard rings.

Hashing uses a splitmix64-based integer mixer (stable across processes and
platforms — Python's builtin hash() is salted and would break determinism).
"""

import math
import random
from dataclasses import dataclass

import numpy as np

from config import Config, DEFAULT_CONFIG
from world import gen_bsp, gen_cave, gen_cavern
from world.tiles import Tile

ChunkKey = tuple[int, int]
Position = tuple[int, int]

_MASK64 = (1 << 64) - 1
_NOISE_SALT = 0xC0FFEE  # keeps distance-noise hashes distinct from other uses


def _mix64(z: int) -> int:
    """splitmix64 finalizer — one mixing round."""
    z = (z + 0x9E3779B97F4A7C15) & _MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
    return z ^ (z >> 31)


def _hash_ints(*values: int) -> int:
    """Deterministic 64-bit hash of a tuple of ints (order-sensitive)."""
    h = 0xA0761D6478BD642F
    for v in values:
        h = _mix64(h ^ _mix64(v & _MASK64))
    return h


@dataclass
class Chunk:
    """One generated chunk: origin coords plus its int8 tile array."""

    cx: int
    cy: int
    tiles: np.ndarray


class ChunkStore:
    """The infinite world: dict of chunks keyed (cx, cy), grown on demand."""

    def __init__(self, config: Config = DEFAULT_CONFIG, world_seed: int | None = None) -> None:
        self._config = config
        self.seed = config.world_seed if world_seed is None else world_seed
        self._chunks: dict[ChunkKey, Chunk] = {}
        self._spawn: Position | None = None

    def __len__(self) -> int:
        return len(self._chunks)

    def chunk_coords(self, x: int, y: int) -> ChunkKey:
        """The chunk containing global tile (x, y); works for negatives."""
        size = self._config.chunk_size
        return x // size, y // size

    def get_chunk(self, cx: int, cy: int) -> Chunk:
        """The chunk at (cx, cy), generating it on first request."""
        key = (cx, cy)
        chunk = self._chunks.get(key)
        if chunk is None:
            chunk = Chunk(cx, cy, _generate_chunk(self.seed, cx, cy, self._config))
            self._chunks[key] = chunk
        return chunk

    def tile_at(self, x: int, y: int) -> Tile:
        """Global-coordinate tile lookup; generates the chunk if missing."""
        size = self._config.chunk_size
        cx, cy = x // size, y // size
        local = self.get_chunk(cx, cy).tiles[y - cy * size, x - cx * size]
        return Tile(local.item())

    def ensure_loaded(self, agent_pos: Position) -> None:
        """Stream chunks within preload_radius (Chebyshev) of the agent."""
        radius = self._config.preload_radius
        cx, cy = self.chunk_coords(agent_pos[0], agent_pos[1])
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                self.get_chunk(cx + dx, cy + dy)

    @property
    def spawn(self) -> Position:
        """Deterministic passable spawn near the world origin.

        The center of chunk (0, 0) is carved FLOOR by the pipeline, so the
        scan hits at distance 0; the rings are belt-and-braces.
        """
        if self._spawn is None:
            self._spawn = self._find_spawn()
        return self._spawn

    def _find_spawn(self) -> Position:
        size = self._config.chunk_size
        mid = size // 2
        for distance in range(size):
            for y in range(mid - distance, mid + distance + 1):
                for x in range(mid - distance, mid + distance + 1):
                    if max(abs(x - mid), abs(y - mid)) != distance:
                        continue
                    if self.tile_at(x, y).passable:
                        return x, y
        raise RuntimeError("no passable tile found in chunk (0, 0)")


def _generate_chunk(seed: int, cx: int, cy: int, config: Config) -> np.ndarray:
    """The full chunk pipeline; pure function of (seed, cx, cy, config)."""
    size = config.chunk_size
    rng = random.Random(_hash_ints(seed, cx, cy) % (1 << 63))
    band = _band_for(seed, cx, cy, config)
    if band == "bsp":
        grid = gen_bsp.generate(
            rng, size, size, config.bsp_min_partition, config.bsp_min_room
        )
        tiles = np.array(
            [[int(tile) for tile in row] for row in grid], dtype=np.int8
        )
    elif band == "cave":
        tiles = gen_cave.generate(
            rng,
            size,
            size,
            config.cave_fill_prob,
            config.cave_smooth_steps,
            config.cave_wall_threshold,
        )
    else:
        tiles = gen_cavern.generate(
            rng,
            size,
            size,
            config.cavern_fill_prob,
            config.cavern_smooth_steps,
            config.cave_wall_threshold,
            config.cavern_pool_chance,
            config.cavern_pool_attempts,
            config.cavern_pool_min_size,
            config.cavern_pool_max_size,
            config.cavern_lava_share,
            (size // 2, size // 2),
        )
    mid = size // 2
    tiles[mid, mid] = int(Tile.FLOOR)
    _drill_seam_corridors(tiles, seed, cx, cy, config)
    _ensure_interior_connected(tiles)
    return tiles


def _band_for(seed: int, cx: int, cy: int, config: Config) -> str:
    """"bsp" | "cave" | "cavern" from the noised distance of the chunk center."""
    mid = config.chunk_size // 2
    gx, gy = cx * config.chunk_size + mid, cy * config.chunk_size + mid
    distance = math.hypot(gx, gy) + _distance_noise(seed, gx, gy, config)
    if distance < config.band_bsp_max:
        return "bsp"
    if distance < config.band_cavern_min:
        return "cave"
    return "cavern"


def _distance_noise(seed: int, gx: int, gy: int, config: Config) -> float:
    """Hashed uniform noise in [-band_blend_noise, +band_blend_noise]."""
    h = _hash_ints(seed, _NOISE_SALT, gx, gy)
    return ((h / (1 << 64)) * 2.0 - 1.0) * config.band_blend_noise


def _edge_jitter(seed: int, kind: str, owner_cx: int, owner_cy: int, config: Config) -> int:
    """Crossing offset from the edge midpoint, shared by both neighbours.

    `kind` is "V" (border east of the owner chunk) or "H" (south of it);
    hashing the canonical owner id — not (chunk, edge-name) — is what makes
    the neighbour compute the identical offset.
    """
    h = _hash_ints(seed, ord(kind), owner_cx, owner_cy)
    span = 2 * config.seam_jitter + 1
    return h % span - config.seam_jitter


def _drill_seam_corridors(
    tiles: np.ndarray, seed: int, cx: int, cy: int, config: Config
) -> None:
    """Carve the four center-to-border L corridors (FLOOR over everything)."""
    size = config.chunk_size
    mid = size // 2
    floor_v = int(Tile.FLOOR)

    def carve_h(x1: int, x2: int, y: int) -> None:
        tiles[y, min(x1, x2) : max(x1, x2) + 1] = floor_v

    def carve_v(y1: int, y2: int, x: int) -> None:
        tiles[min(y1, y2) : max(y1, y2) + 1, x] = floor_v

    # north border is ("H", cx, cy-1); the S corridor of that neighbour
    # uses the same jitter, so both vertical legs share a global column
    jn = _edge_jitter(seed, "H", cx, cy - 1, config)
    carve_h(mid, mid + jn, mid)
    carve_v(0, mid, mid + jn)
    js = _edge_jitter(seed, "H", cx, cy, config)
    carve_h(mid, mid + js, mid)
    carve_v(mid, size - 1, mid + js)
    # west border is ("V", cx-1, cy); the E corridor of that neighbour
    # uses the same jitter, so both horizontal legs share a global row
    jw = _edge_jitter(seed, "V", cx - 1, cy, config)
    carve_v(mid, mid + jw, mid)
    carve_h(0, mid, mid + jw)
    je = _edge_jitter(seed, "V", cx, cy, config)
    carve_v(mid, mid + je, mid)
    carve_h(mid, size - 1, mid + je)


def _ensure_interior_connected(tiles: np.ndarray) -> None:
    """Flood from the chunk center; drill every unreachable FLOOR pocket.

    Pockets are visited in raster order and each is joined to the nearest
    already-reached tile (Chebyshev, raster tie-break) by an L corridor
    (horizontal leg first). Drilling only adds FLOOR, so each iteration
    strictly grows the reached set and the loop terminates.
    """
    size = tiles.shape[0]
    mid = size // 2
    floor_v = int(Tile.FLOOR)
    cells = tiles.tolist()
    while True:
        reached = _flood(cells, mid, mid)
        pocket = None
        for y in range(size):
            for x in range(size):
                if cells[y][x] == floor_v and (x, y) not in reached:
                    pocket = (x, y)
                    break
            if pocket is not None:
                break
        if pocket is None:
            break
        px, py = pocket
        rx, ry = min(
            reached,
            key=lambda p: (max(abs(p[0] - px), abs(p[1] - py)), p[1], p[0]),
        )
        for x in range(min(px, rx), max(px, rx) + 1):
            cells[py][x] = floor_v
        for y in range(min(py, ry), max(py, ry) + 1):
            cells[y][rx] = floor_v
    tiles[:, :] = np.array(cells, dtype=tiles.dtype)


def _flood(cells: list[list[int]], start_x: int, start_y: int) -> set[Position]:
    """Movement-rule flood (8-dir, no corner cutting) over one chunk."""
    size = len(cells)
    floor_v = int(Tile.FLOOR)
    seen = {(start_x, start_y)}
    stack = [(start_x, start_y)]
    while stack:
        x, y = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (
                    not 0 <= nx < size
                    or not 0 <= ny < size
                    or cells[ny][nx] != floor_v
                    or (nx, ny) in seen
                ):
                    continue
                if dx != 0 and dy != 0 and not (
                    cells[y][x + dx] == floor_v and cells[y + dy][x] == floor_v
                ):
                    continue
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen
