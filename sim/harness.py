"""Headless soak harness: stream the chunk world + agent, tick N times, report.

No pygame, no rendering — the referee box for watching EXPLORE range over
the infinite world. The finite map had a coverage denominator; the chunk
world does not, so travel is the coverage signal: chunks generated and max
Chebyshev distance from spawn (Chebyshev because that is the agent's
movement metric — documented choice). Memory size over time stays as the
belief-side growth metric. Everything remains deterministic end to end:
same (n, seed, config) -> identical stats.
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
    memory_tiles: int  # total records (all terrains) in memory
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
    for _ in range(n):
        tick(agent, world, rng, config)
        distance = max(abs(agent.x - spawn[0]), abs(agent.y - spawn[1]))
        max_distance = max(max_distance, distance)
    return SimStats(
        ticks=n,
        seed=seed,
        chunks_generated=len(world),
        max_distance=max_distance,
        memory_tiles=len(agent.memory),
        decisions=agent.explorer.decisions,
        final_position=(agent.x, agent.y),
    )
