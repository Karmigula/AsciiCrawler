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
    """Open floor with whatever monsters you put in it, and maybe a wall."""

    def __init__(self, monsters=(), width=20, wall_at=None):
        self.monsters = list(monsters)
        self.width = width
        self.wall_at = wall_at  # an x to run a wall down, if any

    def tile_at(self, x, y):
        if self.wall_at is not None and x == self.wall_at:
            return Tile.WALL
        inside = -self.width < x < self.width and -self.width < y < self.width
        return Tile.FLOOR if inside else Tile.WALL

    def move_entity(self, monster, x, y):
        monster.x, monster.y = x, y

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


def test_it_does_not_shoot_through_rock():
    """It did, and at things it had never laid eyes on.

    Targeting scanned a square and asked what was standing in it, with no
    reference to sight at all - so a bolt would leave the creature, pass
    through a wall, and hit something on the far side that nothing had seen.
    """
    import random

    from sim.chronicle import Chronicle
    from sim.tick import _cast

    agent = _caster()
    agent.log = Chronicle(limit=10)
    hidden = Monster(kind=TROLL, x=5, y=0, hp=TROLL.hp)

    spent = _cast(agent, Room([hidden], wall_at=3), random.Random(1), DEFAULT_CONFIG)

    assert not spent, "it fired through a wall"
    assert hidden.hp == TROLL.hp
    assert not agent.flashes, "and drew a bolt doing it"


def test_it_shoots_the_same_thing_when_the_way_is_clear():
    """The other half: the fix must not make it refuse honest shots."""
    import random

    from sim.chronicle import Chronicle
    from sim.tick import _cast

    agent = _caster()
    agent.log = Chronicle(limit=10)
    target = Monster(kind=TROLL, x=5, y=0, hp=TROLL.hp)

    assert _cast(agent, Room([target]), random.Random(1), DEFAULT_CONFIG)
    assert target.hp < TROLL.hp


def test_a_bolt_may_cross_water_and_lava():
    """Only rock stops one. Anything else and a caster in the ashfields sulks."""
    from sim.spells import clear_shot

    class Pools(Room):
        def tile_at(self, x, y):
            if x in (2, 3):
                return Tile.LAVA if x == 2 else Tile.WATER
            return Tile.FLOOR

    assert clear_shot(Pools(), (0, 0), (5, 0))


def test_a_monster_does_not_shoot_through_rock_either():
    """A thing that shoots through a wall is not frightening, it is broken."""
    import random

    from agent.loadout import derive
    from sim.ai import take_turns
    from sim.bosses import BOSSES, scaled

    cinder = next(boss for boss in BOSSES if boss.key == "cinderwake")
    kind = scaled(cinder, 5, DEFAULT_CONFIG)

    blocked = Monster(kind=kind, x=4, y=0, hp=kind.hp)
    agent = AgentState(x=0, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.derived = derive(agent.stats, {}, DEFAULT_CONFIG)
    damage, _ = take_turns(
        agent, [blocked], Room([blocked], wall_at=2), random.Random(2), DEFAULT_CONFIG, tick=1
    )

    assert damage == 0, "it shot through the wall"
    assert (blocked.x, blocked.y) != (4, 0), "and it should be closing instead"


def test_it_does_not_shoot_round_a_corner_it_can_see_past():
    """Sight is generous at corners; a bolt is not.

    Field of view is about what an eye catches, so it reports tiles the
    straight line to them clips a wall on the way to - eighty such spots
    around a single block of rock. Without the line check the creature fires
    into the corner and the bolt is drawn through it.
    """
    import random

    from sim.chronicle import Chronicle
    from sim.spells import clear_shot
    from sim.tick import _cast

    class Corner(Room):
        """One block of rock at (-3, -1)."""

        def tile_at(self, x, y):
            if (x, y) == (-3, -1):
                return Tile.WALL
            return Tile.FLOOR

    world = Corner()
    behind = Monster(kind=TROLL, x=-4, y=-1, hp=TROLL.hp)
    world.monsters = [behind]

    assert not clear_shot(world, (0, 0), (-4, -1)), "the layout no longer blocks"

    agent = _caster()
    agent.log = Chronicle(limit=10)
    spent = _cast(agent, world, random.Random(1), DEFAULT_CONFIG)

    assert not spent, "it fired through the corner"
    assert behind.hp == TROLL.hp
