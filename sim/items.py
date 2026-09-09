"""Base item kinds, and the roll that turns a base into an actual item.

Potions and gold carry no stats and never take affixes by design: they are
consumables, not gear, and the loadout evaluator only ever scores the
equippable slots.
"""

import random
from dataclasses import dataclass

from sim.affixes import Affix, roll_affixes, roll_rarity


@dataclass(frozen=True)
class ItemKind:
    """One base item. `slot` is None for anything that is not equippable."""

    key: str
    glyph: str
    slot: str | None
    attack: int = 0
    defense: int = 0


ITEMS: tuple[ItemKind, ...] = (
    ItemKind("weapon", ")", slot="weapon", attack=2),
    ItemKind("armor", "[", slot="armor", defense=2),
    ItemKind("ring", "=", slot="ring", attack=1),
    ItemKind("amulet", '"', slot="amulet", defense=1),
    ItemKind("potion", "!", slot=None),
    ItemKind("gold", "$", slot=None),
)

GRAVE = ItemKind("grave", "+", slot=None)
"""Where the agent died. Not in ITEMS: graves are left, never spawned."""


def roll_for(kind: ItemKind, rng: random.Random, depth: float, config) -> tuple:
    """(rarity, affixes) for a freshly created item of this base kind.

    Unslotted kinds short-circuit: a potion is a potion, and rolling a rarity
    for it would only add noise to every seeded stream downstream.
    """
    if kind.slot is None:
        return "common", ()
    rarity = roll_rarity(rng, depth)
    return rarity, roll_affixes(rng, rarity, config.curse_chance)
