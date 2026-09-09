"""Base item kinds — data only. Affixes, rarity and loadouts are Phase 5.

Potions and gold carry no stats by design: they are consumables, not gear,
and the Phase 5 evaluator will only ever score the equippable slots.
"""

from dataclasses import dataclass


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
