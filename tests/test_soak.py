"""Running many worlds at once."""

import pytest

from config import DEFAULT_CONFIG
from sim.soak import available_workers, run_many, summarise


def test_parallel_and_serial_give_the_same_answers():
    """The point of a deterministic sim: which core ran a world cannot matter."""
    seeds = [1, 2, 3, 4]
    serial = run_many(150, seeds, DEFAULT_CONFIG, workers=1)
    parallel = run_many(150, seeds, DEFAULT_CONFIG, workers=2)
    assert serial == parallel


def test_results_come_back_in_seed_order():
    """Whichever worker finishes first, a batch has to be comparable."""
    seeds = [7, 3, 11]
    results = run_many(120, seeds, DEFAULT_CONFIG, workers=2)
    assert [r.seed for r in results] == seeds


def test_a_single_seed_does_not_start_a_pool():
    result = run_many(120, [5], DEFAULT_CONFIG, workers=8)
    assert len(result) == 1
    assert result[0].seed == 5


def test_no_seeds_is_not_an_error():
    assert run_many(100, [], DEFAULT_CONFIG, workers=4) == []


def test_worker_count_is_clamped_to_something_sane():
    assert available_workers() >= 1
    # More workers than jobs must not spawn idle processes or fail.
    assert len(run_many(100, [1, 2], DEFAULT_CONFIG, workers=64)) == 2
    assert len(run_many(100, [1, 2], DEFAULT_CONFIG, workers=0)) == 2


def test_the_summary_aggregates_the_batch():
    results = run_many(150, [1, 2], DEFAULT_CONFIG, workers=1)
    summary = summarise(results)
    assert summary["worlds"] == 2
    assert summary["ticks_each"] == 150
    assert summary["kills"] == sum(r.kills for r in results)
    assert summary["max_distance"] == max(r.max_distance for r in results)
    assert len(summary["levels"]) == 2


def test_an_empty_batch_summarises_to_nothing():
    assert summarise([]) == {}


def test_a_soak_notices_an_agent_that_stopped_moving():
    """The metric that both missed freezes would have tripped.

    A frozen agent starves for neither reason the other assertions check: its
    memory stays small, it never runs out of frontier, and it quietly stands
    still for the rest of the run.
    """
    result = run_many(600, [3], DEFAULT_CONFIG, workers=1)[0]
    assert result.moved_ticks > result.ticks * 0.8, (
        f"the agent moved on only {result.moved_ticks} of {result.ticks} ticks"
    )


def test_movement_is_counted_per_tick_not_per_step():
    result = run_many(300, [1], DEFAULT_CONFIG, workers=1)[0]
    assert 0 <= result.moved_ticks <= result.ticks


@pytest.mark.slow
def test_many_worlds_survive_a_long_run():
    """Eight seeds rather than one. A single soak is one world's worth of luck,
    and both freezes this suite once missed were seed-specific - they showed up
    where a particular dungeon put a trap or penned the agent between monsters.

    Affordable now that worlds run one per core: eight of these cost about what
    one used to.
    """
    results = run_many(40_000, list(range(1, 9)), DEFAULT_CONFIG, workers=8)

    assert len(results) == 8
    for stats in results:
        where = f"seed {stats.seed}"
        assert stats.moved_ticks > stats.ticks * 0.8, f"{where} stopped moving"
        assert stats.frontier_starved_ticks < stats.ticks // 50, f"{where} starved"
        assert stats.memory_peak < 150_000, f"{where} memory unbounded"
        assert stats.pruned_tiles > 0, f"{where} never forgot anything"
        assert stats.max_distance > 150, f"{where} never got anywhere"
        assert stats.kills > 0, f"{where} never fought"
