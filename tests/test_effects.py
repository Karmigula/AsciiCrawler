"""Blessings, curses, and the totems that hand them out."""

import random

from config import DEFAULT_CONFIG
from sim import effects as status
from sim.session import Session


def test_an_effect_refreshes_rather_than_stacking():
    """Two blessings of might are a longer blessing, not a bigger one.

    Stacking would let a row of effigies bury the creature under modifiers it
    cannot survive losing when they all run out at once.
    """
    active: dict = {}
    status.apply(active, "might")
    status.tick(active)
    status.tick(active)
    status.apply(active, "might")

    assert active["might"] == status.BY_KEY["might"].ticks
    assert len(active) == 1


def test_effects_run_out_and_say_so():
    active = {"might": 2}

    assert status.tick(active) == []
    assert status.tick(active) == ["might"]
    assert active == {}


def test_a_curse_takes_away_what_the_gear_gave():
    """Effects land after equipment, which is what makes a curse a curse."""
    from agent.loadout import derive
    from agent.stats import Stats

    base = Stats.starting(DEFAULT_CONFIG)
    plain = derive(base, {}, DEFAULT_CONFIG)
    cursed = derive(base, {}, DEFAULT_CONFIG, {"weakness": 100, "blindness": 100})

    assert cursed.attack < plain.attack
    assert cursed.fov_radius < plain.fov_radius
    assert cursed.fov_radius >= 1, "a curse must not blind it completely"


def test_the_brain_plans_on_the_sight_a_curse_left_it():
    """Not on the sight it would have had. The effect has to reach the mind."""
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(3)
    before = session.agent.mind(DEFAULT_CONFIG).fov_radius

    status.apply(session.agent.effects, "blindness")
    session.advance(1)

    assert session.agent.mind(DEFAULT_CONFIG).fov_radius < before


def test_the_loadout_notices_an_effect_starting():
    """Derived stats are cached behind a signature; effects are in it now.

    Leaving them out would have been the exact staleness the signature exists
    to prevent - a blessed creature quietly fighting at its old attack.
    """
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(3)
    before = session.agent.derived.attack

    status.apply(session.agent.effects, "might")
    session.advance(1)

    assert session.agent.derived.attack > before


def _first_shrine(world, span=5):
    for cx in range(-span, span + 1):
        for cy in range(-span, span + 1):
            chunk = world.get_chunk(cx, cy)
            if chunk.contents.shrines:
                return chunk.contents.shrines[0]
    return None


def test_every_biome_has_something_to_pray_to():
    from world.biomes import BIOMES

    for biome in BIOMES:
        assert biome.shrine, f"{biome.key} has no shrine"
        assert biome.shrine_glyph == "&"
        assert 0.0 < biome.blessing_chance < 1.0, biome.key


def test_touching_a_totem_does_something_and_only_once():
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(2)
    shrine = _first_shrine(session.world)
    assert shrine is not None, "no shrines were placed; the test proves nothing"

    session.agent.x, session.agent.y = shrine.x, shrine.y
    session.agent.crossed = []
    session.advance(1)

    assert shrine.spent, "the shrine should have answered"
    assert session.agent.effects, "and left something behind"
    assert session.agent.shrines_touched == 1

    before = dict(session.agent.effects)
    session.agent.x, session.agent.y = shrine.x, shrine.y
    session.agent.crossed = []
    session.advance(1)

    assert session.agent.shrines_touched == 1, "a spent shrine answered twice"
    assert set(session.agent.effects) == set(before)


def test_a_totem_can_curse_as_easily_as_bless():
    """Walking to one is a gamble, which is the only reason it is interesting."""
    from world.populate import Shrine

    seen = set()
    for seed in range(60):
        session = Session(DEFAULT_CONFIG, seed=seed, record_hall=False)
        session.advance(2)
        shrine = Shrine(
            x=session.agent.x, y=session.agent.y, kind="a test totem",
            glyph="&", blessing_chance=0.5,
        )
        chunk = session.world.get_chunk(
            *session.world.chunk_coords(session.agent.x, session.agent.y)
        )
        chunk.contents.shrines.append(shrine)
        session.agent.crossed = []
        session.advance(1)
        for key in session.agent.effects:
            seen.add(status.BY_KEY[key].blessing)
        if len(seen) == 2:
            break

    assert seen == {True, False}, f"only ever saw {seen}"


def test_shrines_keep_off_the_doorstep():
    """The first rooms should be about learning to walk, not about gambling."""
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    radius = DEFAULT_CONFIG.shrine_free_radius

    for cx in range(-radius, radius + 1):
        for cy in range(-radius, radius + 1):
            chunk = session.world.get_chunk(cx, cy)
            assert not chunk.contents.shrines, f"shrine at chunk ({cx}, {cy})"


def test_a_totem_is_seen_but_never_picked_up():
    """It is remembered like loot and is not loot: `item_at` never returns one."""
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(2)
    shrine = _first_shrine(session.world)
    assert shrine is not None

    assert session.world.item_at(shrine.x, shrine.y) is None
    assert session.world.shrine_at(shrine.x, shrine.y) is shrine


def test_a_totem_is_worth_walking_to():
    """It used to be worth nothing, so the creature only ever blundered into one.

    A totem is remembered like loot and priced like curiosity: the agent knows
    there is one over there and cannot know what it will do, which is exactly
    the information a creature without x-ray vision would have.
    """
    from agent.goals import expected_upgrade

    assert expected_upgrade("&", {}, DEFAULT_CONFIG, health=1.0) > 0.0


def test_a_bleeding_creature_is_less_curious():
    """A curse at full health is a nuisance; at a fifth of it, it is the end."""
    from agent.goals import expected_upgrade

    healthy = expected_upgrade("&", {}, DEFAULT_CONFIG, health=1.0)
    hurt = expected_upgrade("&", {}, DEFAULT_CONFIG, health=0.2)

    assert hurt < healthy


def test_it_goes_and_touches_totems_rather_than_tripping_over_them():
    """The difference between seeking and blundering, measured."""
    touched = 0
    for seed in (3, 5, 7):
        session = Session(DEFAULT_CONFIG, seed=seed, record_hall=False)
        for _ in range(6000):
            session.advance(1)
        touched += session.agent.shrines_touched

    assert touched >= 6, f"only {touched} totems touched across three worlds"


def test_a_spent_totem_stops_being_interesting():
    """The glyph stays on the floor and memory cannot tell it has gone quiet."""
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(2)
    shrine = _first_shrine(session.world)
    assert shrine is not None

    session.agent.x, session.agent.y = shrine.x, shrine.y
    session.agent.crossed = []
    session.advance(1)

    assert (shrine.x, shrine.y) in session.agent.spent_shrines

    from agent.goals import LootGoal

    decision = LootGoal().decide(
        (shrine.x, shrine.y + 2),
        session.agent.memory,
        session.agent.equipped,
        DEFAULT_CONFIG,
        skip=session.agent.spent_shrines,
    )
    target = decision[0] if decision else None
    assert target != (shrine.x, shrine.y), "it went back to a spent totem"
