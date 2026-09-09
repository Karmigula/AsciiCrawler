"""Pygame-free simulation tick: the agent's seeded random walk."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from world.tiles import Tile

DIRS_4: tuple[tuple[int, int], ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))


@dataclass
class AgentState:
    """What the tick needs to know about the agent: its position."""

    x: int
    y: int


def tick(agent: AgentState, tiles: Sequence[Sequence[Tile]], rng: random.Random) -> None:
    """Move agent in place to a uniformly-chosen adjacent passable tile (4-dir).

    Stays put when no adjacent tile is passable. Deterministic for a fixed
    map and an identically-seeded rng.
    """
    options = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in DIRS_4
        if tiles[agent.y + dy][agent.x + dx] is Tile.FLOOR
    ]
    if options:
        agent.x, agent.y = rng.choice(options)
