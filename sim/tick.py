"""Pygame-free simulation tick: feet, eyes, brain — in that order.

Each tick: act (one step along the current plan, or wander by belief),
observe (FOV at the new position into memory — the only channel from world
truth to belief), think (re-decide when the throttle fires). The brain
never reads `tiles`; only `_try_step` does, as physics: it is where a stale
belief will someday produce a refused step instead of a walk through a wall.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from agent.fov import compute_fov
from agent.goals import DIRS_8, ExploreGoal
from agent.memory import Memory
from config import Config
from world.tiles import Tile


@dataclass
class AgentState:
    """What the tick needs to know about the agent: where it stands,
    what it remembers, and what it is currently chasing."""

    x: int
    y: int
    memory: Memory = field(default_factory=Memory)
    explorer: ExploreGoal = field(default_factory=ExploreGoal)
    tick_count: int = 0


def tick(agent: AgentState, tiles: Sequence[Sequence[Tile]], rng: random.Random, config: Config) -> None:
    """Advance the world by one tick, in place. Deterministic for a fixed
    map, identically-seeded rng, and config."""
    agent.tick_count += 1
    _act(agent, tiles, rng)
    _observe(agent, tiles, config)
    _think(agent, rng, config)


def _act(agent: AgentState, tiles: Sequence[Sequence[Tile]], rng: random.Random) -> None:
    if agent.explorer.path:
        if _try_step(agent, agent.explorer.path[0], tiles):
            agent.explorer.path.pop(0)
        else:
            agent.explorer.drop_plan()  # blocked: physics disagrees with belief
        return
    # idle fallback: wander to a believed-passable neighbour, corner-cut safe
    options = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in DIRS_8
        if _wander_ok(agent, dx, dy)
    ]
    if options:
        _try_step(agent, rng.choice(options), tiles)


def _wander_ok(agent: AgentState, dx: int, dy: int) -> bool:
    if dx != 0 and dy != 0 and not (
        agent.memory.believes_passable((agent.x + dx, agent.y))
        and agent.memory.believes_passable((agent.x, agent.y + dy))
    ):
        return False
    return agent.memory.believes_passable((agent.x + dx, agent.y + dy))


def _try_step(agent: AgentState, nxt: tuple[int, int], tiles: Sequence[Sequence[Tile]]) -> bool:
    """Move one cell if the step is sane and the world agrees it is floor."""
    dx, dy = nxt[0] - agent.x, nxt[1] - agent.y
    if max(abs(dx), abs(dy)) != 1:
        return False
    if not (0 <= nxt[1] < len(tiles) and 0 <= nxt[0] < len(tiles[nxt[1]])):
        return False
    if tiles[nxt[1]][nxt[0]] is not Tile.FLOOR:
        return False
    agent.x, agent.y = nxt
    return True


def _observe(agent: AgentState, tiles: Sequence[Sequence[Tile]], config: Config) -> None:
    fov = compute_fov(tiles, (agent.x, agent.y), config.fov_radius)
    agent.memory.observe({(x, y): tiles[y][x] for x, y in fov}, agent.tick_count)


def _think(agent: AgentState, rng: random.Random, config: Config) -> None:
    if not agent.explorer.wants_rethink(
        agent.memory, agent.tick_count, config.explore_throttle_ticks
    ):
        return
    agent.explorer.decide((agent.x, agent.y), agent.memory, rng, config, agent.tick_count)
