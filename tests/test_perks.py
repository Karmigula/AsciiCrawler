"""Perk triggers firing on sim events."""

from agent.loadout import derive
from agent.stats import Stats
from config import DEFAULT_CONFIG
from sim.affixes import BY_KEY
from sim.items import ITEMS
from sim.monsters import MONSTERS
from sim.perks import EVENTS, on_hit_taken, on_kill
from world.populate import Item, Monster

KINDS = {kind.key: kind for kind in ITEMS}


def _item(base: str, *affix_keys: str) -> Item:
    return Item(
        kind=KINDS[base],
        x=0,
        y=0,
        rarity="rare",
        affixes=tuple(BY_KEY[key] for key in affix_keys),
    )


def _monster(glyph="g"):
    kind = next(k for k in MONSTERS if k.glyph == glyph)
    return Monster(kind=kind, x=0, y=0, hp=kind.hp)


def _derived(equipped):
    return derive(Stats.starting(DEFAULT_CONFIG), equipped, DEFAULT_CONFIG)


def test_the_hook_names_are_a_closed_set():
    """Anything an affix wants to react to has to be one of these."""
    assert set(EVENTS) == {"kill", "hit_taken", "hit_dealt", "step", "equip"}


def test_a_vampiric_kill_heals():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(10)
    result = on_kill(_derived({"weapon": _item("weapon", "vampiric")}), stats, DEFAULT_CONFIG)
    assert result["healed"] == 4
    assert stats.hp == stats.max_hp - 6


def test_healing_stops_at_the_effective_ceiling():
    """A vampiric weapon sustains a fight; it does not inflate the agent."""
    derived = _derived({"weapon": _item("weapon", "vampiric")})
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(1)
    on_kill(derived, stats, DEFAULT_CONFIG)
    assert stats.hp == derived.max_hp


def test_a_full_agent_gains_nothing_from_a_vampiric_kill():
    stats = Stats.starting(DEFAULT_CONFIG)
    result = on_kill(_derived({"weapon": _item("weapon", "vampiric")}), stats, DEFAULT_CONFIG)
    assert result["healed"] == 0


def test_a_hunters_kill_pays_extra_experience():
    stats = Stats.starting(DEFAULT_CONFIG)
    before = stats.xp
    result = on_kill(_derived({"ring": _item("ring", "hunters")}), stats, DEFAULT_CONFIG)
    assert result["bonus_xp"] == 6
    assert stats.xp > before or stats.level > 1


def test_no_triggers_means_nothing_happens():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(10)
    result = on_kill(_derived({"weapon": _item("weapon", "keen")}), stats, DEFAULT_CONFIG)
    assert result == {"healed": 0, "bonus_xp": 0}
    assert stats.hp == stats.max_hp - 10


def test_thorns_wound_the_attacker():
    monster = _monster("o")
    before = monster.hp
    result = on_hit_taken(_derived({"armor": _item("armor", "thorned")}), monster, damage=5)
    assert result["reflected"] == 2
    assert monster.hp == before - 2


def test_thorns_do_not_fire_on_a_blow_that_did_not_land():
    monster = _monster("o")
    before = monster.hp
    on_hit_taken(_derived({"armor": _item("armor", "thorned")}), monster, damage=0)
    assert monster.hp == before


def test_thorns_can_finish_something_off():
    """A rat that keeps biting armour it cannot hurt eventually kills itself."""
    monster = _monster("r")
    derived = _derived({"armor": _item("armor", "thorned")})
    while monster.hp > 0:
        on_hit_taken(derived, monster, damage=1)
    assert monster.hp <= 0
