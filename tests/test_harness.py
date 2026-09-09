from config import DEFAULT_CONFIG
from sim.harness import run_ticks
from world.chunks import ChunkStore

# measured on the chunk world (memory grows unbounded until 4b adds decay,
# so soak cost grows superlinearly): 1200 ticks ~ 9s with wide margin over
# the ~150 ticks the travel assertion needs
SOAK_TICKS = 1200
SOAK_SEED = 5


def test_harness_is_deterministic_under_a_fixed_seed():
    assert run_ticks(300, 9) == run_ticks(300, 9)


def test_agent_travels_farther_as_ticks_grow():
    early = run_ticks(100, SOAK_SEED)
    late = run_ticks(SOAK_TICKS, SOAK_SEED)
    assert late.max_distance > early.max_distance
    assert late.chunks_generated > early.chunks_generated


def test_stats_after_a_short_run():
    stats = run_ticks(60, 3)
    radius = DEFAULT_CONFIG.preload_radius
    assert stats.chunks_generated >= (2 * radius + 1) ** 2  # full preload disk
    assert stats.memory_tiles > 0
    assert stats.decisions >= 1
    assert stats.max_distance > 0  # measured: 23 tiles within 100 ticks


def test_spawn_is_on_a_passable_tile():
    world = ChunkStore(DEFAULT_CONFIG, world_seed=DEFAULT_CONFIG.world_seed)
    x, y = world.spawn
    assert world.tile_at(x, y).passable
