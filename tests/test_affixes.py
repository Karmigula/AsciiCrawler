"""Affix rolling: deterministic, depth-scaled, and never nonsense."""

import random
from collections import Counter
from dataclasses import replace

from config import DEFAULT_CONFIG
from sim.affixes import (
    AFFIX_COUNT,
    AFFIX_POOL,
    COGNITION_FIELDS,
    RARITY_NAMES,
    STAT_FIELDS,
    describe,
    roll_affixes,
    roll_rarity,
)
from sim.items import ITEMS, roll_for
from world.chunks import ChunkStore

WEAPON = next(k for k in ITEMS if k.key == "weapon")
POTION = next(k for k in ITEMS if k.key == "potion")


def test_every_affix_names_a_field_something_actually_reads():
    for affix in AFFIX_POOL:
        if affix.category == "cognition":
            assert affix.field in COGNITION_FIELDS, affix.key
        elif affix.category == "stat":
            assert affix.field in STAT_FIELDS, affix.key
        elif affix.category == "curse":
            assert affix.field in STAT_FIELDS | COGNITION_FIELDS, affix.key
        else:
            assert affix.category == "trigger"


def test_a_negative_stat_affix_is_always_a_curse():
    """On stats, sign means good or bad. On cognition it does not: `craven`
    lowers the flee threshold, which trades exploration for survival — a
    trade-off in both directions, not a penalty."""
    for affix in AFFIX_POOL:
        if affix.field in STAT_FIELDS:
            assert (affix.amount < 0) == affix.is_curse, affix.key


def test_cognition_affixes_push_in_both_directions():
    cognition = [a for a in AFFIX_POOL if a.category == "cognition"]
    assert any(a.amount > 0 for a in cognition)
    assert any(a.amount < 0 for a in cognition)


def test_rarity_decides_how_many_affixes_an_item_gets():
    for rarity in RARITY_NAMES:
        rolled = roll_affixes(random.Random(4), rarity, curse_chance=0.2)
        assert len(rolled) == AFFIX_COUNT[rarity]


def test_an_item_never_rolls_the_same_affix_twice():
    for seed in range(40):
        rolled = roll_affixes(random.Random(seed), "legendary", curse_chance=0.3)
        assert len(set(rolled)) == len(rolled)


def test_depth_fattens_the_rare_tail_without_closing_any_tier():
    def spread(depth):
        return Counter(roll_rarity(random.Random(s), depth) for s in range(3000))

    shallow, deep = spread(0.0), spread(1.0)
    assert deep["legendary"] > shallow["legendary"]
    assert deep["common"] < shallow["common"]
    assert shallow["legendary"] > 0  # still possible at the origin


def test_consumables_never_take_affixes():
    """A potion is a potion; rolling one would only add noise to the stream."""
    rarity, affixes = roll_for(POTION, random.Random(1), 1.0, DEFAULT_CONFIG)
    assert rarity == "common" and affixes == ()


def test_curses_show_up_but_do_not_dominate():
    config = replace(DEFAULT_CONFIG, curse_chance=0.25)
    cursed = sum(
        1
        for seed in range(200)
        if any(a.is_curse for a in roll_for(WEAPON, random.Random(seed), 1.0, config)[1])
    )
    assert 5 < cursed < 150


def test_no_curses_when_the_chance_is_zero():
    config = replace(DEFAULT_CONFIG, curse_chance=0.0)
    for seed in range(50):
        _, affixes = roll_for(WEAPON, random.Random(seed), 1.0, config)
        assert not any(a.is_curse for a in affixes)


def test_naming_reads_as_a_name():
    affixes = tuple(a for a in AFFIX_POOL if a.key in ("keen", "minded"))
    assert describe("sword", affixes) == "keen sword of the long mind"
    assert describe("sword", ()) == "sword"


def test_item_stats_fold_their_affixes_in():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=5)
    for cx in range(16):
        for item in store.get_chunk(cx, 0).contents.items:
            expected_attack = item.kind.attack + sum(
                int(a.amount) for a in item.affixes if a.field == "attack"
            )
            assert item.attack == expected_attack
            assert item.cursed == any(a.is_curse for a in item.affixes)


def test_the_same_chunk_seed_rolls_the_same_loot():
    def loot():
        store = ChunkStore(DEFAULT_CONFIG, world_seed=77)
        return [
            (i.kind.key, i.x, i.y, i.rarity, tuple(a.key for a in i.affixes))
            for i in store.get_chunk(9, -4).contents.items
        ]

    assert loot() == loot()


def test_far_chunks_carry_better_loot_than_the_doorstep():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=5)

    def rare_share(chunks):
        items = [i for cx in chunks for i in store.get_chunk(cx, 0).contents.items]
        slotted = [i for i in items if i.kind.slot is not None]
        assert slotted
        return sum(1 for i in slotted if i.rarity != "common") / len(slotted)

    assert rare_share(range(12, 20)) > rare_share(range(0, 3))
