"""Monster turns: chase, wander, scheduling, and staying inside the rules."""

import random
from dataclasses import replace

from config import DEFAULT_CONFIG
from sim.ai import take_turns
from sim.monsters import MONSTERS
from world.populate import Monster
from world.tiles import Tile


def _kind(glyph: str):
    return next(k for k in MONSTERS if k.glyph == glyph)


def _monster(x: int, y: int, glyph: str = "g") -> Monster:
    kind = _kind(glyph)
    return Monster(kind=kind, x=x, y=y, hp=kind.hp)


class TinyWorld:
    """Open floor with optional walls/liquids, and the entity API sim.ai needs."""

    def __init__(self, monsters=None, blocked=()) -> None:
        self.monsters = list(monsters or [])
        self.blocked = dict(blocked)  # coord -> Tile
        self.moves = 0

    def tile_at(self, x, y) -> Tile:
        return self.blocked.get((x, y), Tile.FLOOR)

    def entity_at(self, x, y):
        for monster in self.monsters:
            if (monster.x, monster.y) == (x, y):
                return monster
        return None

    def move_entity(self, monster, x, y) -> None:
        monster.x, monster.y = x, y
        self.moves += 1


def _turn(world, agent_pos, tick=1, seed=1, config=DEFAULT_CONFIG):
    take_turns(agent_pos, list(world.monsters), world, random.Random(seed), config, tick)


def test_a_monster_that_can_see_the_agent_closes_the_distance():
    monster = _monster(10, 10)
    world = TinyWorld([monster])
    _turn(world, (14, 10))
    assert (monster.x, monster.y) == (11, 10)


def test_a_chase_steps_diagonally_when_that_is_the_line():
    monster = _monster(10, 10)
    world = TinyWorld([monster])
    _turn(world, (14, 14))
    assert (monster.x, monster.y) == (11, 11)


def test_a_monster_out_of_sight_does_not_home_in_on_the_agent():
    """Far monsters mill about; they must not creep straight at the agent."""
    far = DEFAULT_CONFIG.monster_sight_radius + 5
    approaches = 0
    for seed in range(30):
        monster = _monster(0, 0)
        world = TinyWorld([monster])
        _turn(world, (far, 0), seed=seed)
        if monster.x > 0 and monster.y == 0:
            approaches += 1
    assert approaches < 25  # a chase would make this 30


def test_an_idle_monster_sometimes_stays_put():
    config = replace(DEFAULT_CONFIG, monster_wander_chance=0.0)
    monster = _monster(0, 0)
    world = TinyWorld([monster])
    _turn(world, (100, 100), config=config)
    assert (monster.x, monster.y) == (0, 0)


def test_speed_two_monsters_act_every_other_tick():
    """speed is ticks-per-move: an ogre (speed 2) moves on even ticks only."""
    monster = _monster(10, 10, "O")
    world = TinyWorld([monster])
    _turn(world, (14, 10), tick=3)
    assert (monster.x, monster.y) == (10, 10)
    _turn(world, (14, 10), tick=4)
    assert (monster.x, monster.y) == (11, 10)


def test_a_monster_will_not_walk_into_a_wall_or_a_liquid():
    for blocker in (Tile.WALL, Tile.WATER, Tile.LAVA):
        monster = _monster(10, 10)
        world = TinyWorld([monster], blocked={(11, 10): blocker})
        _turn(world, (14, 10))
        assert (monster.x, monster.y) == (10, 10), blocker


def test_monsters_do_not_stack():
    blocker = _monster(11, 10)
    mover = _monster(10, 10)
    world = TinyWorld([blocker, mover])
    _turn(world, (14, 10))
    assert (mover.x, mover.y) == (10, 10)


def test_a_monster_does_not_step_onto_the_agent():
    """Bumping is Phase 4b; until then the agent's tile is simply occupied."""
    monster = _monster(10, 10)
    world = TinyWorld([monster])
    _turn(world, (11, 10))
    assert (monster.x, monster.y) == (10, 10)


def test_a_monster_acts_at_most_once_per_tick():
    monster = _monster(10, 10)
    world = TinyWorld([monster])
    _turn(world, (14, 10), tick=1)
    _turn(world, (14, 10), tick=1)  # same tick handed round twice
    assert world.moves == 1


def test_turn_order_does_not_depend_on_the_order_handed_in():
    """The active list arrives in chunk order, which follows the agent's route."""

    def run(order):
        monsters = [_monster(x, y) for x, y in order]
        world = TinyWorld(monsters)
        take_turns((20, 20), list(monsters), world, random.Random(4), DEFAULT_CONFIG, 1)
        return sorted((m.x, m.y) for m in monsters)

    forward = [(10, 10), (11, 11), (12, 10)]
    assert run(forward) == run(list(reversed(forward)))
