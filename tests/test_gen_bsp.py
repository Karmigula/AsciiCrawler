import random
from collections import deque

from config import DEFAULT_CONFIG
from world.gen_bsp import generate
from world.tiles import Tile

WIDTH = DEFAULT_CONFIG.chunk_size  # BSP now generates per-chunk
HEIGHT = DEFAULT_CONFIG.chunk_size
MIN_PARTITION = DEFAULT_CONFIG.bsp_min_partition
MIN_ROOM = DEFAULT_CONFIG.bsp_min_room


def _gen(seed: int) -> list[list[Tile]]:
    return generate(random.Random(seed), WIDTH, HEIGHT, MIN_PARTITION, MIN_ROOM)


def test_bsp_same_seed_produces_identical_grids():
    assert _gen(42) == _gen(42)


def test_bsp_different_seeds_produce_different_grids():
    assert _gen(1) != _gen(2)


def test_bsp_dimensions_match_request():
    tiles = _gen(42)
    assert len(tiles) == HEIGHT
    assert all(len(row) == WIDTH for row in tiles)


def test_bsp_outer_border_is_all_wall():
    tiles = _gen(42)
    assert all(tiles[0][x] is Tile.WALL for x in range(WIDTH))
    assert all(tiles[HEIGHT - 1][x] is Tile.WALL for x in range(WIDTH))
    assert all(tiles[y][0] is Tile.WALL for y in range(HEIGHT))
    assert all(tiles[y][WIDTH - 1] is Tile.WALL for y in range(HEIGHT))


def test_bsp_grid_contains_both_tile_kinds():
    flat = [tile for row in _gen(42) for tile in row]
    assert Tile.FLOOR in flat
    assert Tile.WALL in flat


def _floor_cells(tiles: list[list[Tile]]) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile is Tile.FLOOR
    }


def _flood_fill(floors: set[tuple[int, int]], start: tuple[int, int]) -> set[tuple[int, int]]:
    reached = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in floors and (nx, ny) not in reached:
                reached.add((nx, ny))
                queue.append((nx, ny))
    return reached


def test_bsp_all_floor_is_mutually_reachable():
    for seed in (7, 42, 1337, 20260909):
        floors = _floor_cells(_gen(seed))
        assert floors, f"seed {seed}: no floor at all"
        reached = _flood_fill(floors, next(iter(floors)))
        assert reached == floors, f"seed {seed}: {len(floors - reached)} unreachable floor cells"


def test_bsp_tiny_map_is_all_wall():
    tiles = generate(random.Random(1), 2, 2, MIN_PARTITION, MIN_ROOM)
    assert all(tile is Tile.WALL for row in tiles for tile in row)
