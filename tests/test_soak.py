"""Running many worlds at once."""

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
