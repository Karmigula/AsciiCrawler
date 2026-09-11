"""A stall in the dark, and how the creature decides what to buy.

Gold had no use. It was a number that went up, which made every coin on the
floor a souvenir - and made the agent right to ignore them. A shop turns the
number into a decision, and the decision is the interesting part.

The reasoning reuses the judgement the agent already applies to loot, which is
the whole point of it being reusable: `loadout.score` says what a set of gear
is worth, so an offer is worth the difference between the best set with it and
the best set without. An epic ring is worth nothing to a creature already
wearing a better one, and the scorer knows that because it is the same scorer
that dressed it in the first place.

What it cannot do is haggle, browse, or come back later. It stands at the
stall, works out which single purchase leaves it best off, buys that, and
walks away. A creature with no memory of prices has no business doing more.
"""

from dataclasses import dataclass, field

from agent.loadout import best_assignment, derive, score
from config import Config
from sim.affixes import AFFIX_COUNT
from sim.items import ITEMS, roll_for

# What a stall charges, before rarity. Steep on purpose: gold should be worth
# stooping for and a purchase should be an event.
BASE_PRICE = 14
RARITY_MULTIPLIER = {
    "common": 1.0,
    "uncommon": 1.8,
    "rare": 3.2,
    "epic": 5.5,
    "legendary": 9.0,
}


@dataclass
class Offer:
    """One thing on the counter, and what it costs."""

    item: object
    price: int
    sold: bool = False


@dataclass
class Stall:
    """A shop: a spot on the floor and three things for sale.

    Three because it is enough to be a choice and few enough that a watcher
    can see what the creature passed over.
    """

    x: int
    y: int
    offers: list = field(default_factory=list)

    @property
    def open(self) -> bool:
        return any(not offer.sold for offer in self.offers)


def price_of(item, config: Config) -> int:
    """What a stall asks for something, from its rarity and what is on it."""
    multiplier = RARITY_MULTIPLIER.get(item.rarity, 1.0)
    extras = AFFIX_COUNT.get(item.rarity, 0)
    return max(1, int(BASE_PRICE * multiplier + 4 * extras))


def stock(rng, depth: float, config: Config, x: int, y: int, count: int = 3) -> list:
    """Roll `count` things worth selling: gear, and usually a potion.

    Gear alone made a stall something the creature walked away from. By the
    time it has a purse it is well dressed, three random items rarely beat a
    set it has been tuning for nine thousand ticks, and the shop was a feature
    that never fired. A potion is the one thing always worth having, and
    choosing between a potion and a sword is a better decision than choosing
    between three swords it does not need.

    No gold on the shelves, which would be absurd, and nothing a stall could
    sell that the creature could not use.
    """
    from world.populate import Item

    sellable = [kind for kind in ITEMS if kind.slot is not None]
    potion = next(kind for kind in ITEMS if kind.key == "potion")
    offers = []
    for index in range(count):
        if index == 0 and rng.random() < config.shop_potion_chance:
            item = Item(kind=potion, x=x, y=y)
            offers.append(Offer(item=item, price=config.shop_potion_price))
            continue
        kind = sellable[rng.randrange(len(sellable))]
        # A stall stocks better than the floor does, which is the only reason
        # to walk to one. Without the bonus its three items are the same three
        # items lying around outside, and a creature that has been tuning a
        # set for hours walks straight past: over nine thousand ticks it
        # reached stalls and bought nothing at all.
        rarity, affixes = roll_for(kind, rng, min(1.0, depth + config.shop_quality), config)
        item = Item(kind=kind, x=x, y=y, rarity=rarity, affixes=affixes)
        offers.append(Offer(item=item, price=price_of(item, config)))
    return offers


def _worth(stats, items, config: Config) -> float:
    """What the best set buildable from `items` is worth."""
    chosen = best_assignment(stats, items, config)
    return score(derive(stats, chosen, config), config)


def choose(
    stats,
    equipped: dict,
    backpack,
    offers,
    gold: int,
    config: Config,
    potions: int = 0,
):
    """Which offer to buy, or None to walk away.

    Each is priced by what it actually adds: the best set the agent could
    build with it, against the best set without. An epic ring is worth nothing
    to a creature already wearing a better one, and the scorer knows that
    because it is the same scorer that dressed it in the first place.

    The best affordable improvement wins, and a tie goes to the cheaper one.
    Value-per-coin was the first rule here and it read wrong on screen: a
    creature with two hundred gold would buy the cheap sword and leave the
    better one on the counter, because the cheap one was more *efficient*.
    Efficiency would matter if it were saving for something; it buys once per
    visit and cannot carry a plan between stalls, so it takes the best thing
    it can pay for.
    """
    owned = [*backpack, *(item for item in equipped.values() if item is not None)]
    without = _worth(stats, owned, config)

    best = None
    best_gain = 0.0
    for offer in offers:
        if offer.sold or offer.price > gold:
            continue
        if offer.item.kind.slot is None:
            # A potion does not go in a slot, so the set scorer cannot see it
            # at all. Priced by shortage instead, on the same scale, so it
            # competes with the gear on the next shelf rather than winning or
            # losing by construction.
            shortage = max(0.0, 1.0 - potions / max(1, config.potion_reserve))
            gain = config.v_potion * shortage
        else:
            gain = _worth(stats, [*owned, offer.item], config) - without
        if gain <= 0:
            continue  # it already has better, and the scorer knows it
        if gain > best_gain or (gain == best_gain and best and offer.price < best.price):
            best, best_gain = offer, gain
    return best
