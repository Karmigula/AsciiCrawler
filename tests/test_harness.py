import random

from config import DEFAULT_CONFIG
from sim.harness import run_ticks, spawn_position
from world.gen_bsp import generate
from world.tiles import Tile

# measured: every tried seed reaches 100% well under 2000 ticks on the
# default 96x54 BSP map; 5000 is a >5x margin and still runs in ~2s
SOAK_TICKS = 5000
SOAK_SEED = 4242


def test_harness_is_deterministic_under_a_fixed_seed():
    first = run_ticks(400, 9)
    second = run_ticks(400, 9)
    assert first == second


def test_coverage_of_reachable_floor_within_budget():
    stats = run_ticks(SOAK_TICKS, SOAK_SEED)
    assert stats.coverage >= 0.85


def test_coverage_actually_grows_with_ticks():
    early = run_ticks(100, 5)
    late = run_ticks(1500, 5)
    assert late.coverage > early.coverage


def test_stats_after_a_short_run():
    stats = run_ticks(50, 3)
    assert 0.0 < stats.coverage <= 1.0
    assert stats.memory_tiles > 0
    assert stats.decisions >= 1


def test_spawn_is_on_a_floor_tile():
    cfg = DEFAULT_CONFIG
    tiles = generate(
        random.Random(cfg.map_seed), cfg.map_width, cfg.map_height,
        cfg.bsp_min_partition, cfg.bsp_min_room,
    )
    x, y = spawn_position(tiles, cfg.map_width // 2, cfg.map_height // 2)
    assert tiles[y][x] is Tile.FLOOR
