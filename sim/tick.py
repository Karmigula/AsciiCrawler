"""Pygame-free simulation tick: feet, eyes, brain — in that order.

The world argument is anything offering `ensure_loaded(position)` and
`tile_at(x, y) -> Tile` (ChunkStore in production, tiny stubs in tests).
Each tick: stream chunks around the agent (a cheap radius check), act (one
step along the current plan, or wander by belief), observe (FOV over a
window of global coordinates fetched through `tile_at` — the only channel
from world truth to belief), think (re-decide when the throttle fires).
The brain never reads world tiles; only `_try_step` does, as physics: it is
where a stale belief will someday produce a refused step instead of a walk
through a wall.

Agent position is unbounded global coordinates; nothing here knows about
chunk boundaries.
"""

import random
from dataclasses import dataclass, field

from agent.fov import compute_fov
from agent.goals import DIRS_8, ExploreGoal
from agent.memory import Memory
from config import Config


@dataclass
class AgentState:
    """What the tick needs to know about the agent: where it stands,
    what it remembers, and what it is currently chasing."""

    x: int
    y: int
    memory: Memory = field(default_factory=Memory)
    explorer: ExploreGoal = field(default_factory=ExploreGoal)
    tick_count: int = 0


def tick(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Advance the world by one tick, in place. Deterministic for a fixed
    world seed, identically-seeded rng, and config."""
    agent.tick_count += 1
    world.ensure_loaded((agent.x, agent.y))
    _act(agent, world, rng)
    _observe(agent, world, config)
    _think(agent, rng, config)


def _act(agent: AgentState, world, rng: random.Random) -> None:
    if agent.explorer.path:
        if _try_step(agent, agent.explorer.path[0], world):
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
        _try_step(agent, rng.choice(options), world)


def _wander_ok(agent: AgentState, dx: int, dy: int) -> bool:
    if dx != 0 and dy != 0 and not (
        agent.memory.believes_passable((agent.x + dx, agent.y))
        and agent.memory.believes_passable((agent.x, agent.y + dy))
    ):
        return False
    return agent.memory.believes_passable((agent.x + dx, agent.y + dy))


def _try_step(agent: AgentState, nxt: tuple[int, int], world) -> bool:
    """Move one cell if the step is sane and the world agrees it is passable."""
    dx, dy = nxt[0] - agent.x, nxt[1] - agent.y
    if max(abs(dx), abs(dy)) != 1:
        return False
    if not world.tile_at(nxt[0], nxt[1]).passable:
        return False
    agent.x, agent.y = nxt
    return True


def _observe(agent: AgentState, world, config: Config) -> None:
    """FOV through a (2r+1)-square window of global tiles around the agent.

    Tiles beyond the window are at distance >= radius and invisible anyway,
    so window semantics equal infinite-world semantics. The window is built
    through `tile_at`, never by reaching into chunk internals.
    """
    radius = config.fov_radius
    origin_x, origin_y = agent.x - radius, agent.y - radius
    window = [
        [world.tile_at(origin_x + lx, origin_y + ly) for lx in range(2 * radius + 1)]
        for ly in range(2 * radius + 1)
    ]
    visible = compute_fov(window, (radius, radius), radius)
    observation = {
        (origin_x + lx, origin_y + ly): window[ly][lx] for lx, ly in visible
    }
    agent.memory.observe(observation, agent.tick_count)


def _think(agent: AgentState, rng: random.Random, config: Config) -> None:
    if not agent.explorer.wants_rethink(
        agent.memory, agent.tick_count, config.explore_throttle_ticks
    ):
        return
    agent.explorer.decide((agent.x, agent.y), agent.memory, rng, config, agent.tick_count)
