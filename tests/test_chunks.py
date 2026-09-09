"""Chunk-world tests: seams (the important ones), determinism, connectivity,
biomes, liquids, streaming, spawn."""

import hashlib

import pytest

from config import DEFAULT_CONFIG
from world.chunks import ChunkStore
from world.tiles import Tile

SIZE = DEFAULT_CONFIG.chunk_size
MID = SIZE // 2
FLOOR = int(Tile.FLOOR)
WATER = int(Tile.WATER)
LAVA = int(Tile.LAVA)

SEEDS = (4242, 17, 20260909)
# grids of adjacent chunks: (cx0, cy0, nx, ny); picked to straddle all three
# biome bands and include negative chunk coordinates
GRIDS = ((-1, -1, 3, 3), (1, 1, 2, 2), (3, 4, 2, 2), (6, 6, 2, 2))
# guaranteed-BSP chunks (center distance 45/101 + blend 48 < 150)
NEAR_CHUNKS = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
# guaranteed cave/cavern chunks (center distance - blend > 150)
FAR_CHUNKS = ((5, 4), (5, 5), (6, 6), (10, 0), (0, 10), (-5, 5), (7, 0), (4, 6))
# guaranteed cavern even at maximum blend noise (distance - 48 > 400)
CAVERNS = ((6, 6), (10, 0), (0, 10))


def _store(seed: int) -> ChunkStore:
    return ChunkStore(DEFAULT_CONFIG, world_seed=seed)


def _digest(store: ChunkStore, cx: int, cy: int) -> str:
    return hashlib.sha256(store.get_chunk(cx, cy).tiles.tobytes()).hexdigest()


def _merged(store: ChunkStore, cx0: int, cy0: int, nx: int, ny: int) -> list[list[int]]:
    """Tile rows of an nx*ny chunk grid starting at (cx0, cy0), global layout."""
    return [
        [
            int(store.get_chunk(cx0 + gx // SIZE, cy0 + gy // SIZE).tiles[gy % SIZE, gx % SIZE])
            for gx in range(nx * SIZE)
        ]
        for gy in range(ny * SIZE)
    ]


def _flood(grid: list[list[int]], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Agent-movement flood (8-dir, no corner cutting) over a merged grid."""
    height, width = len(grid), len(grid[0])
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (
                    not 0 <= nx < width
                    or not 0 <= ny < height
                    or grid[ny][nx] != FLOOR
                    or (nx, ny) in seen
                ):
                    continue
                if dx != 0 and dy != 0 and not (
                    grid[y][x + dx] == FLOOR and grid[y + dy][x] == FLOOR
                ):
                    continue
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def _long_wall_runs(grid: list[list[int]], min_len: int = 7) -> int:
    """Count maximal straight WALL runs >= min_len, both axes (room-likeness:
    measured 244+ on BSP chunks, <= 112 on CA chunks across test seeds)."""
    height, width = len(grid), len(grid[0])
    runs = 0
    for y in range(height):
        run = 0
        for x in range(width + 1):
            if x < width and grid[y][x] != FLOOR:
                run += 1
            else:
                if run >= min_len:
                    runs += 1
                run = 0
    for x in range(width):
        run = 0
        for y in range(height + 1):
            if y < height and grid[y][x] != FLOOR:
                run += 1
            else:
                if run >= min_len:
                    runs += 1
                run = 0
    return runs


# ---------------------------------------------------------------- seams


@pytest.mark.parametrize("seed", SEEDS)
def test_each_shared_border_has_exactly_one_mutually_passable_crossing(seed):
    """The seam invariant, black box: generators keep borders solid WALL, so
    the only mutually-passable adjacent pair on any internal border is the
    seam-corridor crossing — exactly one, near the edge midpoint."""
    for cx0, cy0, nx, ny in GRIDS:
        grid = _merged(_store(seed), cx0, cy0, nx, ny)
        for by in range(cy0, cy0 + ny):
            for bx in range(cx0, cx0 + nx - 1):  # vertical borders
                left = (bx - cx0 + 1) * SIZE - 1
                rows = [
                    (by - cy0) * SIZE + ly
                    for ly in range(SIZE)
                    if grid[(by - cy0) * SIZE + ly][left] == FLOOR
                    and grid[(by - cy0) * SIZE + ly][left + 1] == FLOOR
                ]
                assert len(rows) == 1, f"seed {seed}: V({bx},{by}) crossings {rows}"
                local = rows[0] - (by - cy0) * SIZE
                assert SIZE // 4 <= local < 3 * SIZE // 4
        for by in range(cy0, cy0 + ny - 1):  # horizontal borders
            for bx in range(cx0, cx0 + nx):
                top = (by - cy0 + 1) * SIZE - 1
                cols = [
                    (bx - cx0) * SIZE + lx
                    for lx in range(SIZE)
                    if grid[top][(bx - cx0) * SIZE + lx] == FLOOR
                    and grid[top + 1][(bx - cx0) * SIZE + lx] == FLOOR
                ]
                assert len(cols) == 1, f"seed {seed}: H({bx},{by}) crossings {cols}"
                local = cols[0] - (bx - cx0) * SIZE
                assert SIZE // 4 <= local < 3 * SIZE // 4


@pytest.mark.parametrize("seed", SEEDS)
def test_flood_fill_across_borders_merges_all_floor(seed):
    """Mutual passability, the strong form: one flood from a chunk center
    with the agent's movement rules reaches every FLOOR tile of the grid,
    crossing every internal border through the seam corridors."""
    for cx0, cy0, nx, ny in GRIDS:
        grid = _merged(_store(seed), cx0, cy0, nx, ny)
        start = (MID, MID)  # center of the (cx0, cy0) chunk, grid-local
        floors = {
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile == FLOOR
        }
        assert start in floors
        assert _flood(grid, start) == floors


# ---------------------------------------------------------- determinism


@pytest.mark.parametrize("cx, cy", ((0, 0), (-3, -2), (5, -7), (2, 2), (-1, 1)))
def test_same_seed_and_coords_generate_identical_chunks(cx, cy):
    assert _digest(_store(4242), cx, cy) == _digest(_store(4242), cx, cy)
    assert _digest(_store(4242), cx, cy) != _digest(_store(4243), cx, cy)


def test_chunk_generation_is_independent_of_neighbor_state():
    """No cross-chunk state: a chunk's tiles cannot depend on what was
    generated before it or around it."""
    lone = _store(77)
    expected = _digest(lone, 2, 2)
    surrounded = _store(77)
    for cy in range(1, 4):
        for cx in range(1, 4):
            surrounded.get_chunk(cx, cy)
    assert _digest(surrounded, 2, 2) == expected
    after = _store(77)
    after.get_chunk(2, 2)
    for cy in range(1, 4):
        for cx in range(1, 4):
            after.get_chunk(cx, cy)
    assert _digest(after, 2, 2) == expected


# -------------------------------------------------------- connectivity


@pytest.mark.parametrize("seed", (4242, 7))
@pytest.mark.parametrize("cx, cy", ((0, 0), (1, 1), (3, 3), (6, 6), (-2, -2), (10, 0)))
def test_all_floor_reachable_from_chunk_center(seed, cx, cy):
    """Interior connectivity across all three biomes (BSP, cave, cavern)."""
    grid = _store(seed).get_chunk(cx, cy).tiles.tolist()
    floors = {
        (x, y)
        for y, row in enumerate(grid)
        for x, tile in enumerate(row)
        if tile == FLOOR
    }
    assert (MID, MID) in floors
    assert _flood(grid, (MID, MID)) == floors


# --------------------------------------------------------------- biomes


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_near_origin_chunks_are_room_like(seed):
    """BSP band: long straight wall runs (room walls) — measured >= 244."""
    store = _store(seed)
    for cx, cy in NEAR_CHUNKS:
        grid = store.get_chunk(cx, cy).tiles.tolist()
        assert _long_wall_runs(grid) >= 180, (seed, cx, cy)


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_far_chunks_are_cave_like(seed):
    """CA bands: blobby walls — measured <= 112 long runs."""
    store = _store(seed)
    for cx, cy in FAR_CHUNKS:
        grid = store.get_chunk(cx, cy).tiles.tolist()
        assert _long_wall_runs(grid) < 180, (seed, cx, cy)


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_far_chunks_contain_liquids(seed):
    """Cavern band (statistical, seeded): ponds do form somewhere far out."""
    store = _store(seed)
    liquid = False
    for cx, cy in CAVERNS:
        tiles = store.get_chunk(cx, cy).tiles
        if ((tiles == WATER) | (tiles == LAVA)).any():
            liquid = True
    assert liquid, f"seed {seed}: no liquids in any cavern chunk"


# -------------------------------------------------------------- liquids


@pytest.mark.parametrize("seed", (4242, 7))
def test_liquids_are_impassable_and_never_seal_connectivity(seed):
    store = _store(seed)
    checked = 0
    for cx, cy in CAVERNS:
        tiles = store.get_chunk(cx, cy).tiles
        if not ((tiles == WATER) | (tiles == LAVA)).any():
            continue
        checked += 1
        grid = tiles.tolist()
        assert grid[MID][MID] == FLOOR  # center anchor stays walkable
        floors = {
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile == FLOOR
        }
        assert _flood(grid, (MID, MID)) == floors
    assert checked, "expected at least one liquid chunk in the sample"


# ------------------------------------------------------------ streaming


def test_spawn_is_deterministic_and_passable():
    first, second = _store(4242), _store(4242)
    assert first.spawn == second.spawn
    assert first.spawn == (MID, MID)  # chunk (0, 0) center is carved FLOOR
    assert first.tile_at(*first.spawn).passable


def test_tile_at_maps_global_coords_including_negatives():
    store = _store(4242)
    assert store.tile_at(MID, MID) is Tile(store.get_chunk(0, 0).tiles[MID, MID].item())
    assert store.tile_at(-1, -1) is Tile(store.get_chunk(-1, -1).tiles[SIZE - 1, SIZE - 1].item())
    assert store.tile_at(SIZE, -SIZE) is Tile(store.get_chunk(1, -1).tiles[0, 0].item())
    assert store.tile_at(-SIZE - 5, 3 * SIZE + 2) is Tile(
        store.get_chunk(-2, 3).tiles[SIZE - 5, 2].item()
    )


def test_ensure_loaded_generates_the_preload_radius():
    store = _store(4242)
    assert len(store) == 0
    store.ensure_loaded((MID, MID))
    radius = DEFAULT_CONFIG.preload_radius
    expected = {
        (dx, dy)
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    }
    assert expected <= set(store._chunks.keys())
    assert len(store) == len(expected)
    assert (radius + 1, 0) not in store._chunks  # nothing beyond the radius


def test_ensure_loaded_streams_as_the_agent_moves():
    store = _store(4242)
    store.ensure_loaded((MID, MID))
    before = len(store)
    store.ensure_loaded((MID + 3 * SIZE, MID))  # three chunks east
    assert len(store) > before
    assert (5, 0) in store._chunks


def test_chunks_are_never_discarded():
    store = _store(4242)
    first = store.get_chunk(0, 0)
    for cx in range(-4, 5):
        store.ensure_loaded((cx * SIZE + MID, MID))
    assert store.get_chunk(0, 0) is first  # same object, persistent world
