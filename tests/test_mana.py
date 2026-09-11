"""Mana: what a spell costs, and what it looks like crossing the room."""

from dataclasses import replace

from agent.stats import Stats
from config import DEFAULT_CONFIG
from sim import spells as magic
from sim.session import Session


def test_a_new_creature_has_a_pool_to_cast_from():
    stats = Stats.starting(DEFAULT_CONFIG)

    assert stats.mp == stats.max_mp == DEFAULT_CONFIG.agent_max_mp


def test_spending_asks_and_pays_in_one_go():
    """A caller that checks first and pays later eventually forgets one."""
    stats = Stats.starting(DEFAULT_CONFIG)

    assert stats.spend(5) is True
    assert stats.mp == DEFAULT_CONFIG.agent_max_mp - 5
    assert stats.spend(10_000) is False
    assert stats.mp == DEFAULT_CONFIG.agent_max_mp - 5, "a refused spell costs nothing"


def test_mana_never_goes_past_the_top():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.spend(4)
    stats.recover(100)

    assert stats.mp == stats.max_mp


def test_gear_raises_the_ceiling_it_recovers_to():
    """Worn gear that deepens the pool should be usable, not decorative."""
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.recover(100, ceiling=stats.max_mp + 12)

    assert stats.mp == stats.max_mp + 12


def test_a_spell_out_of_reach_of_the_pool_is_not_offered():
    """Cooldown and cost both gate a cast; `ready` knows about both."""
    off_cooldown = magic.ready(("ember_bolt",), {}, mana=100)
    too_poor = magic.ready(("ember_bolt",), {}, mana=1)

    assert [s.key for s in off_cooldown] == ["ember_bolt"]
    assert too_poor == []


def test_every_spell_costs_something():
    """A free spell is a melee attack with better manners."""
    for spell in magic.SPELLS:
        assert spell.cost > 0, spell.key
        assert spell.cooldown >= 30, f"{spell.key} comes back too fast"


def test_levelling_deepens_the_pool_and_fills_it():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.spend(stats.max_mp)
    before = stats.max_mp

    stats.gain_xp(10_000, DEFAULT_CONFIG)

    assert stats.max_mp > before
    assert stats.mp == stats.max_mp, "a promotion should feel like one"


def test_casting_spends_and_the_pool_trickles_back():
    from sim.affixes import AFFIX_POOL
    from sim.items import ITEMS
    from world.populate import Item

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    embers = next(a for a in AFFIX_POOL if a.key == "embers")
    amulet = next(k for k in ITEMS if k.key == "amulet")
    session.agent.equipped["amulet"] = Item(
        kind=amulet, x=0, y=0, rarity="rare", affixes=(embers,)
    )
    session.advance(1)

    spent_at = None
    for _ in range(4000):
        before = session.agent.casts
        session.advance(1)
        if session.agent.casts > before:
            spent_at = session.agent.stats.mp
            break

    assert spent_at is not None, "it never cast; the test proves nothing"
    assert spent_at < session.agent.derived.max_mp, "casting was free"

    for _ in range(DEFAULT_CONFIG.mp_regen_ticks * 3):
        session.advance(1)
    assert session.agent.stats.mp > spent_at, "the pool never came back"


# --- what it looks like ---


def test_a_bolt_leaves_a_line_from_the_caster_to_the_target():
    path = magic.trail((0, 0), (4, 0))

    assert (0, 0) not in path, "the creature is standing there"
    assert path[-1] == (4, 0), "it should reach what it was aimed at"
    assert len(path) == 4


def test_a_bolt_points_the_way_it_is_going():
    assert magic.bolt_glyph((0, 0), (5, 0)) == "-"
    assert magic.bolt_glyph((0, 0), (0, 5)) == "|"
    assert magic.bolt_glyph((0, 0), (4, 4)) == "\\"
    assert magic.bolt_glyph((0, 0), (4, -4)) == "/"


def test_the_frame_draws_a_bolt_over_the_world():
    import random

    from agent.loadout import derive
    from render.frame import paint_bolts
    from sim.chronicle import Chronicle
    from sim.monsters import MONSTERS
    from sim.tick import AgentState, _cast
    from world.populate import Monster
    from world.tiles import Tile

    class Room:
        def __init__(self, monsters):
            self.monsters = list(monsters)

        def tile_at(self, x, y):
            return Tile.FLOOR if -30 < x < 30 and -30 < y < 30 else Tile.WALL

        def entity_at(self, x, y):
            for monster in self.monsters:
                if (monster.x, monster.y) == (x, y) and monster.hp > 0:
                    return monster
            return None

        def remove_entity(self, monster):
            self.monsters.remove(monster)

        def drop_item(self, *args, **kwargs):
            return None

        def ensure_loaded(self, position):
            pass

    troll = next(kind for kind in MONSTERS if kind.key == "troll")
    agent = AgentState(x=0, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.log = Chronicle(limit=5)
    agent.derived = replace(
        derive(agent.stats, {}, DEFAULT_CONFIG), spells=("ember_bolt",)
    )
    room = Room([Monster(kind=troll, x=5, y=0, hp=99)])

    assert _cast(agent, room, random.Random(1), DEFAULT_CONFIG)
    assert agent.flashes, "nothing was left to draw"

    cells = [[None] * 13 for _ in range(9)]
    cells = paint_bolts(cells, (-6, -4), agent)
    drawn = [cell for row in cells for cell in row if cell]

    assert len(drawn) == 5, f"expected a five-tile bolt, drew {len(drawn)}"
    assert {cell[0] for cell in drawn} == {"-"}


def test_a_bolt_burns_out():
    """Otherwise the room fills up with the last hour of shooting."""
    from sim.tick import AgentState, _fade_flashes

    agent = AgentState(x=0, y=0)
    agent.flashes = [((1, 0), "-", (1, 2, 3), 2)]

    _fade_flashes(agent)
    assert agent.flashes and agent.flashes[0][3] == 1
    _fade_flashes(agent)
    assert agent.flashes == []


def test_a_bolt_off_the_window_is_skipped_rather_than_clamped():
    """Clamping would smear the fight down the edge of the screen."""
    from render.frame import paint_bolts
    from sim.tick import AgentState

    agent = AgentState(x=0, y=0)
    agent.flashes = [((900, 900), "-", (1, 2, 3), 2)]

    cells = [[None] * 5 for _ in range(5)]
    cells = paint_bolts(cells, (0, 0), agent)

    assert all(cell is None for row in cells for cell in row)
