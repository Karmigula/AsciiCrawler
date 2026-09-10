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


def _decaying(ttl: int = 150, interval: int = 25):
    """A fast-forgetting config, so a short run still exercises full decay."""
    from dataclasses import replace

    return replace(DEFAULT_CONFIG, memory_ttl=ttl, memory_prune_interval=interval)


def test_decay_bounds_memory_over_a_long_run():
    """The belief dict tracks recent experience, not lifetime experience.

    Asserted as a plateau rather than as a ratio at one length: the peak has
    to stop growing as the run gets longer, which is the actual property.
    Comparing the two at a single short horizon passes or fails on how far the
    agent happened to wander before the first sweep.
    """
    decaying = _decaying()
    short = run_ticks(1500, 11, decaying)
    long = run_ticks(3000, 11, decaying)

    assert short.pruned_tiles > 0
    assert long.pruned_tiles > short.pruned_tiles, "it keeps forgetting"
    assert long.memory_peak <= short.memory_peak * 1.1, (
        "twice the run should not mean a bigger high-water mark: "
        f"{short.memory_peak} -> {long.memory_peak}"
    )


def test_without_decay_memory_just_grows():
    """The other half of the claim: the plateau is decay's doing, not the
    world running out of tiles."""
    from dataclasses import replace

    forever = replace(DEFAULT_CONFIG, memory_ttl=10**9, memory_prune_interval=25)
    short = run_ticks(1500, 11, forever)
    long = run_ticks(3000, 11, forever)

    assert forever.memory_ttl > 0
    assert short.pruned_tiles == 0
    assert long.memory_peak > short.memory_peak * 1.5


def test_the_agent_keeps_finding_somewhere_to_go():
    """Decay recycles novelty: forgotten ground returns to the frontier."""
    assert run_ticks(800, 11, _decaying()).frontier_starved_ticks == 0


def test_a_decaying_run_is_still_deterministic():
    config = _decaying()
    assert run_ticks(400, 5, config) == run_ticks(400, 5, config)


def test_the_active_scan_stays_bounded_by_the_activation_radius():
    stats = run_ticks(400, 5, _decaying())
    span = 2 * DEFAULT_CONFIG.activation_radius + 1
    assert stats.monsters_seen <= span * span


def test_a_soak_reports_the_danger_it_ran_into():
    """Phase 4 made the world lethal; the referee box should say so."""
    stats = run_ticks(1500, 7, _decaying(ttl=600, interval=50))
    assert stats.kills > 0
    assert stats.damage_taken > 0
    assert stats.final_level >= 1
    assert stats.deaths >= 0


def test_death_does_not_break_determinism():
    config = _decaying(ttl=600, interval=50)
    assert run_ticks(1500, 7, config) == run_ticks(1500, 7, config)
