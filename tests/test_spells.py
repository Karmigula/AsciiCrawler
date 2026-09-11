"""Ranged attacks, the effects they leave, and backing away to use them."""

from dataclasses import replace

from agent.loadout import derive
from agent.stats import Stats
from config import DEFAULT_CONFIG
from sim import spells as magic
from sim.monsters import MONSTERS, afflict, effective_attack, effective_speed, fade
from sim.tick import AgentState, _chebyshev, _kite
from world.populate import Monster
from world.tiles import Tile

TROLL = next(kind for kind in MONSTERS if kind.key == "troll")
RAT = next(kind for kind in MONSTERS if kind.key == "rat")


class Room:
    """Open floor with whatever monsters you put in it."""

    def __init__(self, monsters=(), width=20):
        self.monsters = list(monsters)
        self.width = width

    def tile_at(self, x, y):
        inside = -self.width < x < self.width and -self.width < y < self.width
        return Tile.FLOOR if inside else Tile.WALL

    def entity_at(self, x, y):
        for monster in self.monsters:
            if (monster.x, monster.y) == (x, y):
                return monster
        return None

    def ensure_loaded(self, position):
        pass

    def remove_entity(self, monster):
        """A killed monster leaves the room, the way the real world does."""
        if monster in self.monsters:
            self.monsters.remove(monster)

    def drop_item(self, kind, x, y, rng=None, item=None):
        return None


def _caster(spells=("ember_bolt",), cooldowns=None):
    agent = AgentState(x=0, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.derived = replace(derive(agent.stats, {}, DEFAULT_CONFIG), spells=spells)
    agent.cooldowns = dict(cooldowns or {})
    return agent


def test_a_spell_is_ready_until_it_is_used():
    assert [s.key for s in magic.ready(("spark",), {})] == ["spark"]
    assert magic.ready(("spark",), {"spark": 3}) == []


def test_the_heaviest_ready_spell_goes_first():
    """Leading with the small one wastes the window the big one needed."""
    order = [s.key for s in magic.ready(("spark", "ember_bolt"), {})]

    assert order[0] == "ember_bolt"


def test_cooldowns_count_down_and_clear():
    cooldowns = {"spark": 2}
    magic.tick(cooldowns)
    assert cooldowns == {"spark": 1}
    magic.tick(cooldowns)
    assert cooldowns == {}


def test_a_chilled_monster_acts_less_often_and_a_withered_one_hits_softer():
    """How something small makes a fight with something big winnable."""
    monster = Monster(kind=TROLL, x=0, y=0, hp=TROLL.hp)
    speed, attack = effective_speed(monster), effective_attack(monster)

    afflict(monster, "chilled")
    afflict(monster, "withered")

    assert effective_speed(monster) > speed
    assert effective_attack(monster) < attack


def test_a_monster_effect_wears_off():
    monster = Monster(kind=TROLL, x=0, y=0, hp=TROLL.hp)
    afflict(monster, "chilled")
    for _ in range(200):
        fade(monster)

    assert monster.effects == {}
    assert effective_speed(monster) == TROLL.speed


def test_an_effect_never_stops_a_monster_entirely():
    """Chilled should be a handicap, not a stun: it still gets to act."""
    monster = Monster(kind=TROLL, x=0, y=0, hp=TROLL.hp)
    for _ in range(5):
        afflict(monster, "chilled")
        afflict(monster, "withered")

    assert effective_speed(monster) >= 1
    assert effective_attack(monster) >= 1


def test_it_backs_away_from_something_big_while_reloading():
    agent = _caster(cooldowns={"ember_bolt": 9})
    troll = Monster(kind=TROLL, x=1, y=0, hp=TROLL.hp)
    before = _chebyshev((agent.x, agent.y), (troll.x, troll.y))

    moved = _kite(agent, Room([troll]), DEFAULT_CONFIG)

    assert moved
    assert _chebyshev((agent.x, agent.y), (troll.x, troll.y)) > before


def test_it_does_not_back_away_from_a_rat():
    """Retreating from a rat reads as cowardice, and the rat follows anyway."""
    agent = _caster(cooldowns={"ember_bolt": 9})

    assert not _kite(agent, Room([Monster(kind=RAT, x=1, y=0, hp=RAT.hp)]), DEFAULT_CONFIG)


def test_it_shoots_rather_than_shuffles_when_something_is_ready():
    """Kiting is for the reload. With a spell up, distance is not the problem."""
    agent = _caster(cooldowns={})

    assert not _kite(agent, Room([Monster(kind=TROLL, x=1, y=0, hp=TROLL.hp)]), DEFAULT_CONFIG)


def test_a_creature_with_no_spells_never_kites():
    """It has nothing to do with the distance, so backing off is just fleeing."""
    agent = _caster(spells=(), cooldowns={"ember_bolt": 5})

    assert not _kite(agent, Room([Monster(kind=TROLL, x=1, y=0, hp=TROLL.hp)]), DEFAULT_CONFIG)


def test_cornered_it_turns_and_fights():
    """There is nowhere to back away to, and shuffling in place is worse."""
    agent = _caster(cooldowns={"ember_bolt": 9})
    # Boxed in: every way out is occupied or wall.
    crowd = [
        Monster(kind=TROLL, x=dx, y=dy, hp=TROLL.hp)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx or dy)
    ]

    assert not _kite(agent, Room(crowd), DEFAULT_CONFIG)


def test_casting_kills_at_a_distance_and_starts_the_cooldown():
    """The whole point: hurting something it is not standing next to."""
    import random

    from sim.chronicle import Chronicle
    from sim.tick import _cast

    agent = _caster()
    agent.log = Chronicle(limit=10)
    rat = Monster(kind=RAT, x=4, y=0, hp=RAT.hp)
    room = Room([rat])

    spent = _cast(agent, room, random.Random(1), DEFAULT_CONFIG)

    assert spent, "it had a bolt and something to aim at"
    assert rat.hp <= 0, "a rat should not survive an ember bolt"
    assert agent.cooldowns.get("ember_bolt", 0) > 0
    assert agent.casts == 1


def test_nothing_is_cast_at_something_out_of_reach():
    import random

    from sim.chronicle import Chronicle
    from sim.tick import _cast

    agent = _caster()
    agent.log = Chronicle(limit=10)
    far = Monster(kind=RAT, x=15, y=0, hp=RAT.hp)

    assert not _cast(agent, Room([far]), random.Random(1), DEFAULT_CONFIG)
    assert far.hp == RAT.hp
