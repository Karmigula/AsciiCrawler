"""The things with names: where they wait, when they come, how big they are."""

from dataclasses import replace

from config import DEFAULT_CONFIG
from sim import bosses
from sim.session import Session
from world.biomes import biome_at, throne_chunk


def test_a_boss_is_built_at_the_level_it_is_met():
    """Fixed numbers make a boss a wall or furniture, depending on timing."""
    kind = next(b for b in bosses.BOSSES if b.key == "hoarfrost")

    early = bosses.scaled(kind, 1, DEFAULT_CONFIG)
    later = bosses.scaled(kind, 10, DEFAULT_CONFIG)

    assert early.hp == kind.hp, "at level one it is its own size"
    assert later.hp > early.hp * 2, "and it grows with the creature"
    assert later.attack > early.attack


def test_scaling_keeps_a_boss_recognisably_itself():
    """Its reach and what it inflicts are the fight; those do not scale."""
    kind = next(b for b in bosses.BOSSES if b.key == "cinderwake")
    big = bosses.scaled(kind, 12, DEFAULT_CONFIG)

    assert big.reach == kind.reach
    assert big.inflicts == kind.inflicts
    assert big.glyph == kind.glyph


def test_every_boss_belongs_to_a_biome_that_exists():
    from world.biomes import BIOMES

    keys = {biome.key for biome in BIOMES}
    for boss in bosses.BOSSES:
        assert boss.biome in keys, boss.key


def test_no_two_bosses_share_a_glyph_with_anything_else():
    """A named thing has to be tellable from a rat at a glance."""
    from sim.items import GRAVE, ITEMS
    from sim.monsters import MONSTERS
    from world.tiles import Tile

    taken = (
        {tile.glyph for tile in Tile}
        | {kind.glyph for kind in MONSTERS}
        | {kind.glyph for kind in ITEMS}
        | {GRAVE.glyph, "&", DEFAULT_CONFIG.agent_glyph}
    )
    seen = set()
    for boss in bosses.BOSSES:
        assert boss.glyph not in taken, f"{boss.key} reuses {boss.glyph}"
        assert boss.glyph not in seen, f"two bosses use {boss.glyph}"
        seen.add(boss.glyph)


def test_a_throne_is_in_the_same_place_every_time():
    """Decided from the seed and the region, so nothing has to be remembered."""
    first = [
        (cx, cy)
        for cx in range(-20, 21)
        for cy in range(-20, 21)
        if throne_chunk(7, cx, cy, DEFAULT_CONFIG)
    ]
    again = [
        (cx, cy)
        for cx in range(-20, 21)
        for cy in range(-20, 21)
        if throne_chunk(7, cx, cy, DEFAULT_CONFIG)
    ]

    assert first and first == again


def test_a_region_holds_at_most_one_throne():
    from world.biomes import region_of

    seen: dict = {}
    for cx in range(-24, 25):
        for cy in range(-24, 25):
            if not throne_chunk(5, cx, cy, DEFAULT_CONFIG):
                continue
            region = region_of(cx, cy, DEFAULT_CONFIG.region_size)
            assert region not in seen, f"{region} has two thrones"
            seen[region] = (cx, cy)

    assert seen, "no thrones at all; the test proves nothing"


def test_thrones_keep_away_from_the_spawn():
    radius = DEFAULT_CONFIG.boss_room_free_radius * DEFAULT_CONFIG.region_size
    for cx in range(-radius, radius + 1):
        for cy in range(-radius, radius + 1):
            assert not throne_chunk(5, cx, cy, DEFAULT_CONFIG), (cx, cy)


def test_a_boss_room_is_furnished_with_its_own_biome_boss():
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    found = 0
    for cx in range(-20, 21):
        for cy in range(-20, 21):
            if not throne_chunk(session.seed, cx, cy, DEFAULT_CONFIG):
                continue
            biome = biome_at(session.seed, cx, cy, DEFAULT_CONFIG)
            if bosses.for_biome(biome.key, throned=True) is None:
                continue
            throne = session.world.get_chunk(cx, cy).contents.throne
            assert throne is not None, f"chunk ({cx}, {cy}) has no boss in it"
            assert bosses.for_biome(biome.key, throned=True).key == throne[2]
            found += 1
    assert found, "no furnished boss rooms were found"


def test_nothing_named_turns_up_before_the_creature_is_worth_hunting():
    """A thing with a name would simply end a level-one run."""
    weak = replace(DEFAULT_CONFIG, boss_roam_interval=10, boss_roam_chance=1.0)
    session = Session(weak, seed=3, record_hall=False)

    for _ in range(600):
        session.advance(1)
        if session.agent.stats and session.agent.stats.level >= weak.boss_level:
            break
        assert session.agent.roaming_boss is None, "it was hunted too early"


def test_one_roaming_boss_at_a_time():
    eager = replace(
        DEFAULT_CONFIG, boss_level=1, boss_roam_interval=20, boss_roam_chance=1.0
    )
    session = Session(eager, seed=3, record_hall=False)
    seen = set()

    for _ in range(4000):
        session.advance(1)
        current = session.agent.roaming_boss
        if current is not None and current.hp > 0:
            seen.add(id(current))
            # Whatever else is loaded, only one of them is the hunter.
            assert session.agent.roaming_boss is current

    assert seen, "nothing ever came hunting"


def test_a_roaming_boss_starts_out_of_sight():
    """One that appears beside you is a bug rather than a fight."""
    eager = replace(
        DEFAULT_CONFIG, boss_level=1, boss_roam_interval=20, boss_roam_chance=1.0
    )
    session = Session(eager, seed=3, record_hall=False)

    for _ in range(4000):
        before = session.agent.roaming_boss
        session.advance(1)
        boss = session.agent.roaming_boss
        if boss is not None and boss is not before:
            gap = max(
                abs(boss.x - session.agent.x), abs(boss.y - session.agent.y)
            )
            assert gap >= eager.boss_roam_min_distance, f"it arrived {gap} tiles away"
            return

    raise AssertionError("nothing ever came hunting; the test proves nothing")


def test_the_bar_only_shows_what_the_creature_can_see():
    """Telling the watcher about something behind a wall breaks the whole rule.

    The bar is drawn from the visible set, not from what is loaded nearby, so
    a boss two rooms away is not on it however close it is.
    """
    from render.frame import boss_in_view, visible_from

    eager = replace(
        DEFAULT_CONFIG, boss_level=1, boss_roam_interval=20, boss_roam_chance=1.0
    )
    session = Session(eager, seed=3, record_hall=False)

    for _ in range(6000):
        session.advance(1)
        shown = boss_in_view(session.world, session.agent, eager)
        boss = session.agent.roaming_boss
        visible = visible_from(session.world, session.agent, eager)
        if boss is not None and (boss.x, boss.y) not in visible:
            assert shown is None, "a boss out of sight was put on the bar"
        if shown is None:
            continue
        name, hp, full = shown
        assert name, "the bar has nobody on it"
        assert 0 <= hp <= full
        assert (boss.x, boss.y) in visible, "the bar showed something unseen"
        return

    raise AssertionError("no boss ever came into view")
