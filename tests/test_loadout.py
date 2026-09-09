"""The loadout evaluator: folding gear into numbers, and picking the best set."""

from dataclasses import replace

from agent.loadout import (
    EQUIP_SLOTS,
    active_synergies,
    archetype,
    best_assignment,
    derive,
    effective_config,
    score,
)
from agent.stats import Stats
from config import DEFAULT_CONFIG
from sim.affixes import BY_KEY
from sim.items import ITEMS
from world.populate import Item

KINDS = {kind.key: kind for kind in ITEMS}


def _item(base: str, *affix_keys: str) -> Item:
    return Item(
        kind=KINDS[base],
        x=0,
        y=0,
        rarity="rare",
        affixes=tuple(BY_KEY[key] for key in affix_keys),
    )


def _stats() -> Stats:
    return Stats.starting(DEFAULT_CONFIG)


def test_naked_derived_stats_are_just_the_body():
    derived = derive(_stats(), {}, DEFAULT_CONFIG)
    assert derived.attack == DEFAULT_CONFIG.agent_attack
    assert derived.defense == DEFAULT_CONFIG.agent_defense
    assert derived.fov_radius == DEFAULT_CONFIG.fov_radius
    assert derived.triggers == {}


def test_stat_affixes_and_base_stats_both_fold_in():
    derived = derive(_stats(), {"weapon": _item("weapon", "keen")}, DEFAULT_CONFIG)
    expected = DEFAULT_CONFIG.agent_attack + KINDS["weapon"].attack + 2
    assert derived.attack == expected


def test_a_curse_subtracts():
    cursed = derive(_stats(), {"armor": _item("armor", "brittle")}, DEFAULT_CONFIG)
    plain = derive(_stats(), {"armor": _item("armor")}, DEFAULT_CONFIG)
    assert cursed.defense == plain.defense - 3


def test_cognition_affixes_change_how_the_agent_thinks():
    derived = derive(
        _stats(),
        {"ring": _item("ring", "farsighted"), "amulet": _item("amulet", "minded")},
        DEFAULT_CONFIG,
    )
    assert derived.fov_radius == DEFAULT_CONFIG.fov_radius + 3
    assert derived.memory_ttl == DEFAULT_CONFIG.memory_ttl + 2000


def test_cognition_reaches_the_brain_through_one_config():
    """Every consumer reads one Config, so mind-altering gear cannot be
    forgotten at some call site."""
    derived = derive(_stats(), {"ring": _item("ring", "farsighted")}, DEFAULT_CONFIG)
    mind = effective_config(DEFAULT_CONFIG, derived)
    assert mind.fov_radius == DEFAULT_CONFIG.fov_radius + 3
    assert mind.memory_ttl == derived.memory_ttl
    assert mind.flee_threat == derived.flee_threat
    # untouched knobs are carried through unchanged
    assert mind.chunk_size == DEFAULT_CONFIG.chunk_size


def test_cognition_values_are_clamped_to_something_usable():
    """Stacked curses must not produce a blind agent with a zero-radius view."""
    derived = derive(
        _stats(),
        {"ring": _item("ring", "blinkered"), "amulet": _item("amulet", "blinkered")},
        replace(DEFAULT_CONFIG, fov_radius=2),
    )
    assert derived.fov_radius >= 1


def test_triggers_accumulate_rather_than_overwrite():
    derived = derive(
        _stats(),
        {"weapon": _item("weapon", "vampiric"), "ring": _item("ring", "vampiric")},
        DEFAULT_CONFIG,
    )
    assert derived.triggers["on_kill_heal"] == 8


def test_a_synergy_makes_the_whole_worth_more_than_its_parts():
    """The claim the table exists to make."""
    stats = _stats()
    axe = _item("weapon", "cruel")
    charm = _item("amulet", "vampiric")
    both = score(derive(stats, {"weapon": axe, "amulet": charm}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    naked = score(derive(stats, {}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    axe_only = score(derive(stats, {"weapon": axe}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    charm_only = score(derive(stats, {"amulet": charm}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    assert both > (axe_only - naked) + (charm_only - naked) + naked
    assert any(s.key == "bloodletter" for s in active_synergies(
        derive(stats, {"weapon": axe, "amulet": charm}, DEFAULT_CONFIG)
    ))


def test_a_synergy_can_outbid_a_curse():
    """A cursed item that completes a pairing is still the right choice - the
    decision the whole loot system exists to produce."""
    stats = _stats()
    clean = _item("amulet")
    cursed_but_completing = _item("amulet", "vampiric", "brittle")
    worn = {"weapon": _item("weapon", "cruel")}
    with_clean = score(derive(stats, {**worn, "amulet": clean}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    with_cursed = score(
        derive(stats, {**worn, "amulet": cursed_but_completing}, DEFAULT_CONFIG),
        DEFAULT_CONFIG,
    )
    assert with_cursed > with_clean


def test_the_search_finds_a_known_optimum():
    stats = _stats()
    poor = _item("weapon", "dull")
    good = _item("weapon", "cruel")
    chosen = best_assignment(stats, [poor, good], DEFAULT_CONFIG)
    assert chosen["weapon"] is good


def test_the_search_beats_greedy_when_synergies_couple_the_slots():
    """Greedy picks the best item per slot; that is not the best set."""
    stats = _stats()
    # Solo, the plated amulet scores better than the vampiric one. Together
    # with the axe, the vampiric one completes bloodletter and wins.
    axe = _item("weapon", "cruel")
    sturdy_charm = _item("amulet", "bulwark")
    vampiric_charm = _item("amulet", "vampiric")
    solo_sturdy = score(derive(stats, {"amulet": sturdy_charm}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    solo_vampiric = score(
        derive(stats, {"amulet": vampiric_charm}, DEFAULT_CONFIG), DEFAULT_CONFIG
    )
    assert solo_sturdy > solo_vampiric, "fixture: greedy would take the sturdy one"

    chosen = best_assignment(stats, [axe, sturdy_charm, vampiric_charm], DEFAULT_CONFIG)
    assert chosen["amulet"] is vampiric_charm


def test_the_search_leaves_a_slot_empty_rather_than_wear_junk():
    stats = _stats()
    junk = _item("ring", "brittle", "dull")
    chosen = best_assignment(stats, [junk], DEFAULT_CONFIG)
    assert chosen.get("ring") is None


def test_the_search_only_ever_fills_real_slots():
    stats = _stats()
    chosen = best_assignment(
        stats, [_item("potion"), _item("gold"), _item("weapon", "keen")], DEFAULT_CONFIG
    )
    assert set(chosen) <= set(EQUIP_SLOTS)
    assert "potion" not in chosen


def test_an_empty_inventory_wears_nothing():
    assert best_assignment(_stats(), [], DEFAULT_CONFIG) == {}


def test_archetype_names_the_synergy_when_there_is_one():
    derived = derive(
        _stats(),
        {"weapon": _item("weapon", "cruel"), "amulet": _item("amulet", "vampiric")},
        DEFAULT_CONFIG,
    )
    assert "bloodletter" in archetype(derived, DEFAULT_CONFIG)


def test_archetype_falls_back_to_a_leaning():
    label = archetype(derive(_stats(), {}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    assert label in {"brute", "turtle", "scout", "wanderer"}


def test_recklessness_is_priced():
    """A bold amulet has to earn its keep against the risk it adds."""
    stats = _stats()
    bold = derive(stats, {"amulet": _item("amulet", "bold")}, DEFAULT_CONFIG)
    plain = derive(stats, {"amulet": _item("amulet")}, DEFAULT_CONFIG)
    assert bold.flee_threat > plain.flee_threat
    assert score(bold, DEFAULT_CONFIG) < score(plain, DEFAULT_CONFIG) + (
        DEFAULT_CONFIG.v_flee_penalty * 1.5
    )
