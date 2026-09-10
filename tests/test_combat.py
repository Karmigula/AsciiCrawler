"""Bump combat, experience, and what happens when something runs out of hp."""

import random
from dataclasses import replace

from agent.stats import Stats
from config import DEFAULT_CONFIG
from sim.combat import agent_hits_monster, monster_hits_agent, roll_damage, xp_for
from sim.monsters import MONSTERS
from world.populate import Monster

NO_VARIANCE = replace(DEFAULT_CONFIG, damage_variance=0)


def _monster(glyph="g", x=0, y=0):
    kind = next(k for k in MONSTERS if k.glyph == glyph)
    return Monster(kind=kind, x=x, y=y, hp=kind.hp)


def test_damage_is_attack_minus_defense():
    assert roll_damage(9, 3, random.Random(1), NO_VARIANCE) == 6


def test_damage_never_falls_below_one():
    """Nothing is completely immune to anything — a rat can still scratch."""
    assert roll_damage(1, 99, random.Random(1), NO_VARIANCE) == 1


def test_variance_stays_inside_its_configured_band():
    config = replace(DEFAULT_CONFIG, damage_variance=3)
    rolls = {roll_damage(5, 1, random.Random(s), config) for s in range(40)}
    assert min(rolls) >= 4 and max(rolls) <= 7


def test_the_agent_wounds_what_it_hits():
    monster = _monster("O")
    before = monster.hp
    dealt = agent_hits_monster(Stats.starting(NO_VARIANCE), monster, random.Random(1), NO_VARIANCE)
    assert dealt > 0
    assert monster.hp == before - dealt


def test_a_monster_wounds_the_agent():
    stats = Stats.starting(NO_VARIANCE)
    dealt = monster_hits_agent(_monster("T"), stats, random.Random(1), NO_VARIANCE)
    assert stats.hp == stats.max_hp - dealt


def test_armour_blunts_a_weak_blow_but_never_stops_it():
    stats = Stats.starting(replace(NO_VARIANCE, agent_defense=100))
    dealt = monster_hits_agent(_monster("r"), stats, random.Random(1), NO_VARIANCE)
    assert dealt == 1


def test_deeper_monsters_are_worth_more_experience():
    worths = [xp_for(_monster(k.glyph), DEFAULT_CONFIG) for k in MONSTERS]
    assert worths == sorted(worths)
    assert worths[0] < worths[-1]


def test_stats_take_applies_damage_and_never_heals():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(5)
    assert stats.hp == stats.max_hp - 5
    stats.take(-100)  # a negative blow must not be a potion
    assert stats.hp == stats.max_hp - 5


def test_an_agent_out_of_hit_points_is_not_alive():
    stats = Stats.starting(DEFAULT_CONFIG)
    assert stats.alive
    stats.take(stats.max_hp)
    assert not stats.alive


def test_levelling_raises_the_ceiling_and_heals_to_it():
    """The only healing in the game: a level-up is what saves the agent."""
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(20)
    gained = stats.gain_xp(stats.xp_to_next(DEFAULT_CONFIG), DEFAULT_CONFIG)
    assert gained == 1
    assert stats.level == 2
    assert stats.max_hp == DEFAULT_CONFIG.agent_max_hp + DEFAULT_CONFIG.level_hp_gain
    assert stats.hp == stats.max_hp
    assert stats.attack == DEFAULT_CONFIG.agent_attack + DEFAULT_CONFIG.level_attack_gain


def test_one_windfall_can_pay_for_several_levels():
    stats = Stats.starting(DEFAULT_CONFIG)
    assert stats.gain_xp(100_000, DEFAULT_CONFIG) > 3


def test_each_level_costs_more_than_the_last():
    stats = Stats.starting(DEFAULT_CONFIG)
    costs = []
    for _ in range(4):
        costs.append(stats.xp_to_next(DEFAULT_CONFIG))
        stats.gain_xp(costs[-1], DEFAULT_CONFIG)
    assert costs == sorted(costs)
    assert costs[0] < costs[-1]


def test_levelling_never_takes_hit_points_away():
    """With +max_hp gear the body's own maximum is below the effective one.
    Healing to the bare-body maximum would make a promotion wound you."""
    from agent.loadout import derive
    from sim.affixes import BY_KEY
    from sim.items import ITEMS
    from world.populate import Item

    kinds = {k.key: k for k in ITEMS}
    stats = Stats.starting(DEFAULT_CONFIG)
    armour = Item(
        kind=kinds["armor"], x=0, y=0, rarity="rare", affixes=(BY_KEY["giants"],)
    )
    derived = derive(stats, {"armor": armour}, DEFAULT_CONFIG)
    assert derived.max_hp > stats.max_hp
    stats.hp = derived.max_hp  # full, by the effective ceiling

    stats.gain_xp(stats.xp_to_next(DEFAULT_CONFIG), DEFAULT_CONFIG, ceiling=derived.max_hp)

    assert stats.hp >= derived.max_hp, "levelling up must not wound the agent"


def test_levelling_still_heals_a_wounded_agent():
    stats = Stats.starting(DEFAULT_CONFIG)
    stats.take(20)
    stats.gain_xp(stats.xp_to_next(DEFAULT_CONFIG), DEFAULT_CONFIG)
    assert stats.hp == stats.max_hp
