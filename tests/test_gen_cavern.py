import random

import numpy as np

from config import DEFAULT_CONFIG
from world.gen_cavern import _grow_pools, generate
from world.tiles import Tile

WATER = int(Tile.WATER)
LAVA = int(Tile.LAVA)
FLOOR = int(Tile.FLOOR)
WALL = int(Tile.WALL)


def _gen(seed: int):
    return _gen_with_pool_chance(seed, DEFAULT_CONFIG.cavern_pool_chance)


def _gen_with_pool_chance(seed: int, pool_chance: float):
    cfg = DEFAULT_CONFIG
    return generate(
        random.Random(seed),
        cfg.chunk_size,
        cfg.chunk_size,
        cfg.cavern_fill_prob,
        cfg.cavern_smooth_steps,
        cfg.cave_wall_threshold,
        pool_chance,
        cfg.cavern_pool_attempts,
        cfg.cavern_pool_min_size,
        cfg.cavern_pool_max_size,
        cfg.cavern_lava_share,
        (cfg.chunk_size // 2, cfg.chunk_size // 2),
    )


def _liquids(tiles) -> int:
    return int(((tiles == WATER) | (tiles == LAVA)).sum())


def test_cavern_same_seed_produces_identical_grids():
    assert _gen(42).tobytes() == _gen(42).tobytes()


def test_cavern_outer_border_is_all_wall():
    tiles = _gen(42).tolist()
    size = DEFAULT_CONFIG.chunk_size
    assert all(tile == WALL for tile in tiles[0])
    assert all(tile == WALL for tile in tiles[size - 1])
    assert all(row[0] == WALL for row in tiles)
    assert all(row[size - 1] == WALL for row in tiles)


def test_cavern_center_stays_floor():
    mid = DEFAULT_CONFIG.chunk_size // 2
    for seed in (42, 7, 99):
        assert _gen(seed)[mid, mid].item() == FLOOR


def test_caverns_grow_liquid_pools_across_seeds():
    """Statistical, seeded: default pond params produce liquids somewhere."""
    assert any(_liquids(_gen(seed)) > 0 for seed in range(12))


def _reach(cells, start):
    """4-dir FLOOR flood, the conservative rule gen_cavern's guard uses."""
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= nx < len(cells[0])
                and 0 <= ny < len(cells)
                and cells[ny][nx] == FLOOR
                and (nx, ny) not in seen
            ):
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def _main_component(cells):
    """Largest 4-dir FLOOR body — raw CA leaves natural orphan pockets, so
    "connected" here means the main cavity, not the whole grid."""
    unseen = {
        (x, y)
        for y, row in enumerate(cells)
        for x, tile in enumerate(row)
        if tile == FLOOR
    }
    best = set()
    while unseen:
        component = _reach(cells, min(unseen))
        unseen -= component
        if len(component) > len(best):
            best = component
    return best


def test_cavern_pools_never_break_floor_connectivity():
    """Pools may flood floor, but must never cut floor off.

    The property is differential: against the same seed generated with no
    pools, the main cavity must lose exactly the tiles that became liquid
    and not one tile more. (Whole-grid connectivity is not gen_cavern's to
    promise — the chunk pipeline drills orphan pockets afterwards.)
    """
    for seed in range(12):
        dry = _gen_with_pool_chance(seed, 0.0).tolist()
        wet = _gen_with_pool_chance(seed, DEFAULT_CONFIG.cavern_pool_chance).tolist()
        baseline = _main_component(dry)
        liquid = {
            (x, y)
            for y, row in enumerate(wet)
            for x, tile in enumerate(row)
            if tile in (WATER, LAVA)
        }
        survivors = baseline - liquid
        if not survivors:
            continue
        anchor = min(survivors)
        assert _reach(wet, anchor) == survivors, f"seed {seed}: pool cut the cavity"


def _two_chambers() -> np.ndarray:
    """15x7 grid: two 5x5 chambers joined by a 1-wide corridor on row 3."""
    grid = np.full((7, 15), WALL, dtype=np.int8)
    grid[1:6, 0:5] = FLOOR
    grid[1:6, 10:15] = FLOOR
    grid[3, 5:10] = FLOOR
    return grid


def _floor_index(tiles, point) -> int:
    """Index of `point` in the compact raster-ordered FLOOR list _grow_pools
    builds — what its `rng.randrange(len(floors))` actually selects."""
    cells = tiles.tolist()
    floors = [
        (x, y)
        for y, row in enumerate(cells)
        for x, tile in enumerate(row)
        if tile == FLOOR
    ]
    return floors.index(point)


class _ScriptedRng:
    """Deterministic rng stand-in: pools always attempt, seeded pond spot."""

    def __init__(self, seed_index: int, size: int) -> None:
        self._seed_index = seed_index
        self._size = size

    def random(self) -> float:
        return 0.9  # passes pool_chance (< 1.0); lava_share rolls WATER

    def randrange(self, n: int) -> int:
        return self._seed_index

    def randint(self, low: int, high: int) -> int:
        return self._size


def test_pool_that_would_seal_connectivity_is_reverted():
    """A pond covering the only corridor is verified and rolled back."""
    tiles = _two_chambers()
    seed_index = _floor_index(tiles, (7, 3))  # the corridor midpoint
    _grow_pools(tiles, _ScriptedRng(seed_index, 8), 1.0, 1, 8, 8, 0.3, (2, 3))
    cells = tiles.tolist()
    assert not any(WATER in row or LAVA in row for row in cells)
    assert sum(row.count(FLOOR) for row in cells) == 25 + 25 + 5  # untouched


def test_pool_that_keeps_connectivity_is_committed():
    """A pond inside one chamber stays: liquids appear, floors stay whole."""
    tiles = _two_chambers()
    seed_index = _floor_index(tiles, (2, 1))  # inside the left chamber
    _grow_pools(tiles, _ScriptedRng(seed_index, 8), 1.0, 1, 8, 8, 0.3, (12, 3))
    cells = tiles.tolist()
    assert any(WATER in row for row in cells)
    assert cells[3][12] == FLOOR  # center untouched
