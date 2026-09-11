"""The stall, and how the creature decides what to buy."""

from config import DEFAULT_CONFIG
from sim.affixes import BY_KEY
from sim.items import ITEMS
from sim.shop import Offer, choose, price_of, stock
from world.populate import Item

WEAPON = next(kind for kind in ITEMS if kind.key == "weapon")
ARMOR = next(kind for kind in ITEMS if kind.key == "armor")
POTION = next(kind for kind in ITEMS if kind.key == "potion")


def _item(kind, rarity="common", affixes=()):
    return Item(
        kind=kind, x=0, y=0, rarity=rarity, affixes=tuple(BY_KEY[k] for k in affixes)
    )


def _stats():
    from agent.stats import Stats

    return Stats.starting(DEFAULT_CONFIG)


def test_a_rarer_thing_costs_more():
    cheap = price_of(_item(WEAPON, "common"), DEFAULT_CONFIG)
    dear = price_of(_item(WEAPON, "legendary", ["cruel"]), DEFAULT_CONFIG)

    assert dear > cheap * 3


def test_it_buys_the_best_thing_it_can_afford():
    """Not the most efficient one: it buys once and cannot save for later."""
    cheap = Offer(_item(WEAPON, "uncommon", ["keen"]), 20)
    dear = Offer(_item(WEAPON, "epic", ["cruel", "keen", "hale"]), 90)

    rich = choose(_stats(), {}, [], [cheap, dear], 200, DEFAULT_CONFIG)
    poor = choose(_stats(), {}, [], [cheap, dear], 50, DEFAULT_CONFIG)

    assert rich is dear
    assert poor is cheap


def test_it_walks_away_from_things_it_cannot_afford():
    dear = Offer(_item(WEAPON, "epic", ["cruel"]), 90)

    assert choose(_stats(), {}, [], [dear], 5, DEFAULT_CONFIG) is None


def test_it_walks_away_from_things_it_already_beats():
    """The same scorer that dressed it knows an upgrade from a downgrade."""
    worn = {"weapon": _item(WEAPON, "legendary", ["cruel", "keen", "hale", "giants"])}
    junk = Offer(_item(WEAPON, "common"), 14)

    assert choose(_stats(), worn, [], [junk], 500, DEFAULT_CONFIG) is None


def test_a_potion_is_worth_buying_when_it_has_none():
    """Gear alone made a stall something it always walked away from."""
    potion = Offer(_item(POTION), DEFAULT_CONFIG.shop_potion_price)

    empty_handed = choose(_stats(), {}, [], [potion], 100, DEFAULT_CONFIG, potions=0)
    well_stocked = choose(_stats(), {}, [], [potion], 100, DEFAULT_CONFIG, potions=20)

    assert empty_handed is potion
    assert well_stocked is None


def test_a_stall_stocks_three_things_and_prices_them_all():
    import random

    offers = stock(random.Random(4), 0.5, DEFAULT_CONFIG, 0, 0)

    assert len(offers) == 3
    for offer in offers:
        assert offer.price > 0
        assert offer.item.kind.key != "gold", "a stall selling coins is absurd"


def test_a_stall_stocks_better_than_the_floor_does():
    """Otherwise it is three of the same items lying around outside.

    A creature that has been tuning a set for hours walks straight past those,
    which is exactly what it did: it reached stalls and bought nothing at all.
    """
    import random

    from sim.affixes import RARITY_NAMES

    def rarities(quality):
        from dataclasses import replace

        config = replace(DEFAULT_CONFIG, shop_quality=quality)
        seen = []
        for seed in range(60):
            for offer in stock(random.Random(seed), 0.0, config, 0, 0):
                if offer.item.kind.slot is not None:
                    seen.append(RARITY_NAMES.index(offer.item.rarity))
        return sum(seen) / len(seen)

    assert rarities(DEFAULT_CONFIG.shop_quality) > rarities(0.0)


def test_the_creature_spends_its_gold_and_keeps_the_thing():
    from sim.session import Session
    from world.populate import Stall

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    session.agent.gold = 300
    here = (session.agent.x, session.agent.y)
    chunk = session.world.get_chunk(*session.world.chunk_coords(*here))
    chunk.contents.stalls.append(
        Stall(
            x=here[0],
            y=here[1],
            offers=[Offer(_item(WEAPON, "epic", ["cruel", "keen", "hale"]), 90)],
        )
    )
    session.agent.crossed = []

    session.advance(1)

    assert session.agent.purchases == 1
    assert session.agent.gold == 210
    owned = [*session.agent.backpack, *session.agent.equipped.values()]
    assert any(item is not None and item.rarity == "epic" for item in owned)


def test_it_does_not_stand_at_a_counter_it_cannot_use():
    """It did: one run spent 3,208 ticks re-deciding to visit the same stall."""
    from sim.session import Session
    from world.populate import Stall

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    session.agent.gold = 0
    here = (session.agent.x, session.agent.y)
    chunk = session.world.get_chunk(*session.world.chunk_coords(*here))
    stall = Stall(x=here[0], y=here[1], offers=[Offer(_item(WEAPON, "epic"), 90)])
    chunk.contents.stalls.append(stall)
    session.agent.crossed = []

    session.advance(1)

    assert (stall.x, stall.y) in session.agent.declined_stalls


def test_a_fatter_purse_is_a_reason_to_look_again():
    """Nothing got cheaper, but it can pay now, so the stall is worth another look."""
    from sim.tick import AgentState, _uninteresting

    agent = AgentState(x=0, y=0)
    agent.declined_stalls = {(5, 5): 30}

    agent.gold = 30
    assert (5, 5) in _uninteresting(agent)

    agent.gold = 120
    assert (5, 5) not in _uninteresting(agent)


def test_a_spell_is_worth_something_to_the_scorer():
    """It was worth nothing, so the creature would not pick one up on purpose.

    A focus is the only way it can hurt something it is not standing next to,
    and the loadout scorer could not see that at all.
    """
    from agent.loadout import derive, score

    stats = _stats()
    plain = score(derive(stats, {"amulet": _item(ARMOR)}, DEFAULT_CONFIG), DEFAULT_CONFIG)
    amulet = next(kind for kind in ITEMS if kind.key == "amulet")
    focus = _item(amulet, "rare", ["embers"])
    with_spell = score(derive(stats, {"amulet": focus}, DEFAULT_CONFIG), DEFAULT_CONFIG)

    assert with_spell > plain
