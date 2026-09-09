"""Monster turns: wander, chase, and the speed scheduler. World-side, not brain-side.

The asymmetry with the agent is deliberate. The agent's brain reads memory and
may be confidently wrong about the world; monsters read world truth directly.
They are not characters with beliefs, they are the hazard the character has
beliefs *about* — giving them their own fog would cost a great deal and change
almost nothing an observer could see.

Only monsters in the activation radius are handed to `take_turns`. That is
load-bearing rather than an optimisation: if distant monsters moved too, the
world would simulate itself differently depending on where the agent had
happened to walk, and a chunk's contents would stop being a function of its
seed.

Scheduling is `tick % speed == 0` — speed 1 acts every tick, speed 2 every
other. It is phase-locked rather than per-monster energy so that a monster's
schedule does not depend on when it was first activated, which would otherwise
smuggle the agent's route into the world's behaviour.
"""

import random

from agent.pathing import DIRS_8
from config import Config

Position = tuple[int, int]


def take_turns(
    agent_pos: Position,
    active: list,
    world,
    rng: random.Random,
    config: Config,
    tick: int,
) -> None:
    """Move every active monster that is due to act, in place.

    Iteration order is sorted by position, never dict order: the active list
    arrives in chunk-generation order, which depends on the agent's route.
    """
    for monster in sorted(active, key=lambda m: (m.y, m.x)):
        if monster.last_moved_tick == tick:
            continue
        if tick % max(1, monster.kind.speed):
            continue
        monster.last_moved_tick = tick
        target = _choose_step(monster, agent_pos, rng, config)
        if target is not None:
            _step(monster, target, agent_pos, world)


def _choose_step(monster, agent_pos: Position, rng: random.Random, config: Config):
    """Where this monster wants to go: toward the agent, or idly, or nowhere."""
    if _chebyshev((monster.x, monster.y), agent_pos) <= config.monster_sight_radius:
        return _toward(monster, agent_pos)
    if rng.random() >= config.monster_wander_chance:
        return None
    dx, dy = DIRS_8[rng.randrange(len(DIRS_8))]
    return monster.x + dx, monster.y + dy


def _toward(monster, agent_pos: Position) -> Position:
    """One greedy step along the line to the agent.

    Greedy, not A*: a chase runs every tick for every active monster, and the
    cost of real pathfinding there is not repaid by the behaviour. A monster
    that snags on a wall corner looks like a monster that snagged on a corner.
    """
    step_x = _sign(agent_pos[0] - monster.x)
    step_y = _sign(agent_pos[1] - monster.y)
    return monster.x + step_x, monster.y + step_y


def _step(monster, target: Position, agent_pos: Position, world) -> None:
    """Take the step if the world allows it. Bumping is Phase 4b."""
    if target == (monster.x, monster.y) or target == agent_pos:
        return
    if not world.tile_at(*target).passable:
        return
    if world.entity_at(*target) is not None:
        return  # monsters do not stack
    world.move_entity(monster, *target)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _chebyshev(a: Position, b: Position) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
