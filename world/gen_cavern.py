"""Large-radius CA caverns with water/lava pools — the far biome band.

Same cellular automata as gen_cave (more open: lower fill, extra smoothing
pass), then seeded blobs of FLOOR are flooded to liquid.

Pools are grown, not carved: each attempt picks a seeded FLOOR tile, BFS-
grows a pond of a seeded size over FLOOR (so pools are blobby and stop at
walls), tentatively commits it, then floods from the chunk center — if any
FLOOR that was reachable before the pond became unreachable, the pond sealed
connectivity and is reverted (the brief's "verify reachability before
committing a pool"). The center tile itself is never pooled. A pond grown in
a side component disconnected from the center changes nothing for the main
cavity and commits — those are natural pocket pools.
"""

import random

import numpy as np

from world.gen_cave import ca_walls
from world.tiles import Tile

Point = tuple[int, int]


def generate(
    rng: random.Random,
    width: int,
    height: int,
    fill_prob: float,
    smooth_steps: int,
    wall_threshold: int,
    pool_chance: float,
    pool_attempts: int,
    pool_min_size: int,
    pool_max_size: int,
    lava_share: float,
    center: Point,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: cavern with possible pools."""
    walls = ca_walls(rng, width, height, fill_prob, smooth_steps, wall_threshold)
    tiles = np.where(walls, int(Tile.WALL), int(Tile.FLOOR)).astype(np.int8)
    tiles[center[1], center[0]] = int(Tile.FLOOR)  # protected anchor
    _grow_pools(
        tiles, rng, pool_chance, pool_attempts, pool_min_size, pool_max_size, lava_share, center
    )
    return tiles


def _grow_pools(
    tiles: np.ndarray,
    rng: random.Random,
    pool_chance: float,
    attempts: int,
    min_size: int,
    max_size: int,
    lava_share: float,
    center: Point,
) -> None:
    """In place: grow seeded liquid ponds, reverting any that seal the floor."""
    height, width = tiles.shape
    floor_v = int(Tile.FLOOR)
    cells = tiles.tolist()
    floors = [
        (x, y)
        for y in range(height)
        for x in range(width)
        if cells[y][x] == floor_v
    ]
    if not floors:
        return
    anchor = _main_anchor(cells, floors, center)
    for _ in range(attempts):
        if rng.random() >= pool_chance:
            continue
        seed = floors[rng.randrange(len(floors))]
        size = rng.randint(min_size, max_size)
        pond = _grow(cells, seed, size)
        if not pond or center in pond or anchor in pond:
            continue
        liquid = int(Tile.LAVA) if rng.random() < lava_share else int(Tile.WATER)
        reached_before = _flood(cells, anchor)
        for px, py in pond:
            cells[py][px] = liquid
        reached_after = _flood(cells, anchor)
        if len(reached_after) < len(reached_before) - len(pond & reached_before):
            for px, py in pond:  # sealed something: revert this pool
                cells[py][px] = floor_v
    tiles[:, :] = np.array(cells, dtype=tiles.dtype)


def _main_anchor(cells: list[list[int]], floors: list[Point], center: Point) -> Point:
    """Pick the pool guard's flood anchor: a tile of the largest FLOOR body.

    `generate` forces `center` to FLOOR as the pipeline's carve anchor, which
    in raw CA output can leave it a one-tile island. Flooding the guard from
    such a center would see a cavity of size 1, find nothing to protect and
    wave every pool through. Anchoring on the largest component instead keeps
    the guard meaningful; `center` is preferred when it is already in it, so
    the common case floods from exactly where the seams will carve.
    """
    unseen = set(floors)
    best: set[Point] = set()
    while unseen:
        component = _flood(cells, min(unseen))
        unseen -= component
        if len(component) > len(best):
            best = component
    if not best:
        return center
    return center if center in best else min(best)

def _grow(cells: list[list[int]], seed: Point, size: int) -> set[Point]:
    """BFS-grown blob of up to `size` FLOOR tiles from `seed` (4-dir)."""
    height, width = len(cells), len(cells[0])
    floor_v = int(Tile.FLOOR)
    if cells[seed[1]][seed[0]] != floor_v:
        return set()
    pond = {seed}
    queue = [seed]
    while queue and len(pond) < size:
        x, y = queue.pop(0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and cells[ny][nx] == floor_v
                and (nx, ny) not in pond
            ):
                pond.add((nx, ny))
                queue.append((nx, ny))
                if len(pond) >= size:
                    break
    return pond


def _flood(cells: list[list[int]], center: Point) -> set[Point]:
    """4-dir FLOOD flood from center (stricter than movement: conservative)."""
    height, width = len(cells), len(cells[0])
    floor_v = int(Tile.FLOOR)
    if cells[center[1]][center[0]] != floor_v:
        return set()
    seen = {center}
    stack = [center]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and cells[ny][nx] == floor_v
                and (nx, ny) not in seen
            ):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen
