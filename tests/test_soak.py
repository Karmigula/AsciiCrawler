"""The long soak: does the whole machine survive being left running?

Deselected by default (see pytest.ini). The 100k run takes about 35 minutes
and the whole marked suite about 57: the cost
per tick grows with the size of memory, because `goals.frontier` rescans every
remembered tile on each decision, and by the end the agent remembers tens of
thousands. That is the next thing worth optimising if the soak ever needs to
be routine. It is the
only test that exercises the interaction of every system at once over a span
where slow leaks and slow starvation would show up, so it asserts the three
properties that a long run can break and a short one cannot:

- it does not raise,
- memory stays bounded (decay keeps up with discovery),
- the agent keeps finding somewhere to go (novelty keeps recycling).
"""

import pytest

from config import DEFAULT_CONFIG
from sim.harness import run_ticks

TICKS = 100_000


@pytest.mark.slow
def test_a_hundred_thousand_ticks_of_everything_at_once():
    stats = run_ticks(TICKS, seed=4242)

    assert stats.ticks == TICKS
    # Bounded belief: the pruner has to keep pace with exploration forever.
    assert stats.memory_peak < 120_000, stats
    assert stats.pruned_tiles > 0, stats
    # Novelty keeps recycling: a starved agent is a stuck aquarium.
    assert stats.frontier_starved_ticks < TICKS // 100, stats
    # The creature actually lived: travelled, fought, and found things.
    assert stats.max_distance > 200, stats
    assert stats.chunks_generated > 20, stats
    assert stats.kills > 0, stats
    assert stats.pickups > 0, stats

    # Measured at 100k on seed 4242: 0 starved ticks, 532 tiles travelled,
    # 38,561 peak memory against 528,130 records pruned, 1,939 kills, level 15.
    # Before the review fixes this same run was starved for 82,278 of its
    # 100,000 ticks and never got further than 350 tiles from spawn.


@pytest.mark.slow
def test_a_long_run_is_reproducible():
    """Determinism has to survive length, not just a few hundred ticks."""
    assert run_ticks(20_000, seed=99) == run_ticks(20_000, seed=99)
