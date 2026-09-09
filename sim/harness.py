"""Headless soak harness: stream the chunk world + agent, tick N times, report.

No pygame, no rendering — the referee box for watching EXPLORE range over
the infinite world. The finite map had a coverage denominator; the chunk
world does not, so travel is the coverage signal: chunks generated and max
Chebyshev distance from spawn (Chebyshev because that is the agent's
movement metric — documented choice).

With decay in play the belief-side metrics matter as much as the travel ones.
`memory_peak` is the high-water mark of the memory dict: it is the assertion
that forgetting actually bounds the agent's world model over a long run, which
a final-tick reading alone would miss (a sweep could have just fired). And
`frontier_starved_ticks` counts ticks where the explorer yielded — it looked
for somewhere to go and found no reachable frontier. Decay is supposed to keep
recycling novelty, so a run that starves has lost the thing this phase exists
to provide. (It reads the goal's own flag rather than recomputing the frontier
per tick: the frontier scan is O(memory) and would dominate a long soak.)
"""

import random
from dataclasses import dataclass

from config import DEFAULT_CONFIG, Config
from sim.tick import AgentState, tick
from world.chunks import ChunkStore

Position = tuple[int, int]


@dataclass(frozen=True)
class SimStats:
    """What a soak run measured."""

    ticks: int
    seed: int
    chunks_generated: int
    max_distance: int  # Chebyshev tiles from spawn, sampled every tick
    memory_tiles: int  # total records (all terrains) in memory at the end
    memory_peak: int  # high-water mark of the same, sampled every tick
    pruned_tiles: int  # records dropped by the pruner across the run
    monsters_seen: int  # peak size of the bounded active-entity scan
    frontier_starved_ticks: int  # ticks with no frontier left to aim at
    decisions: int  # EXPLORE decisions made
    final_position: Position


def run_ticks(n: int, seed: int, config: Config = DEFAULT_CONFIG) -> SimStats:
    """Stream the world from `seed`, run the agent for n ticks, measure.

    Deterministic end to end: same (n, seed, config) -> identical stats.
    """
    world = ChunkStore(config, world_seed=seed)
    spawn = world.spawn
    rng = random.Random(seed + 1)
    agent = AgentState(x=spawn[0], y=spawn[1])
    max_distance = 0
    memory_peak = 0
    monsters_seen = 0
    starved = 0
    for _ in range(n):
        tick(agent, world, rng, config)
        distance = max(abs(agent.x - spawn[0]), abs(agent.y - spawn[1]))
        max_distance = max(max_distance, distance)
        memory_peak = max(memory_peak, len(agent.memory))
        monsters_seen = max(monsters_seen, len(agent.active_entities))
        if agent.explorer.yielded:
            starved += 1
    return SimStats(
        ticks=n,
        seed=seed,
        chunks_generated=len(world),
        max_distance=max_distance,
        memory_tiles=len(agent.memory),
        memory_peak=memory_peak,
        pruned_tiles=agent.pruned_total,
        monsters_seen=monsters_seen,
        frontier_starved_ticks=starved,
        decisions=agent.explorer.decisions,
        final_position=(agent.x, agent.y),
    )
