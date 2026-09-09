"""Affixes: what makes one sword different from another sword.

Four categories, and the last one is the interesting one:

- `stat`      — plain numbers on the body (attack, defense, max hp).
- `trigger`   — perks that fire on a sim event (a kill, a blow taken).
- `curse`     — negative modifiers that ride along on otherwise good items,
                so the loadout evaluator has something real to weigh.
- `cognition` — modifiers to how the agent *thinks*: how far it sees, how long
                it remembers, how easily it frightens, how much it values the
                unknown. These are the point of the system. A ring that widens
                the field of view changes the behaviour you watch, not just a
                number on a sheet, and an amulet that makes the agent braver
                and more forgetful produces a visibly different creature.

An affix names the field it modifies and the amount. Nothing here knows how
those fields are applied — `agent/loadout.py` folds stat and cognition affixes
into derived values, and `sim/perks.py` dispatches the triggers.
"""

import random
from dataclasses import dataclass

Slot = str


@dataclass(frozen=True)
class Affix:
    """One modifier. `field` names what it changes; `amount` is signed."""

    key: str
    label: str
    category: str  # stat | trigger | curse | cognition
    field: str
    amount: float

    @property
    def is_curse(self) -> bool:
        return self.category == "curse"


# Fields a cognition affix may touch. Anything outside this set is a bug, and
# the loadout evaluator asserts against it rather than silently doing nothing.
COGNITION_FIELDS = frozenset(
    {"fov_radius", "memory_ttl", "flee_threat", "w_explore", "threat_radius"}
)

STAT_FIELDS = frozenset({"attack", "defense", "max_hp"})

AFFIX_POOL: tuple[Affix, ...] = (
    # --- stats -----------------------------------------------------------
    Affix("keen", "keen", "stat", "attack", 2),
    Affix("cruel", "cruel", "stat", "attack", 4),
    Affix("plated", "plated", "stat", "defense", 2),
    Affix("bulwark", "of the bulwark", "stat", "defense", 4),
    Affix("hale", "hale", "stat", "max_hp", 8),
    Affix("giants", "of giants", "stat", "max_hp", 16),
    # --- triggers --------------------------------------------------------
    Affix("vampiric", "vampiric", "trigger", "on_kill_heal", 4),
    Affix("thorned", "thorned", "trigger", "on_hit_taken_reflect", 2),
    Affix("hunters", "of the hunter", "trigger", "on_kill_xp", 6),
    # --- curses ----------------------------------------------------------
    Affix("brittle", "brittle", "curse", "defense", -3),
    Affix("dull", "dull", "curse", "attack", -3),
    Affix("sickly", "sickly", "curse", "max_hp", -10),
    Affix("blinkered", "blinkered", "curse", "fov_radius", -3),
    # --- cognition -------------------------------------------------------
    Affix("farsighted", "farsighted", "cognition", "fov_radius", 3),
    Affix("minded", "of the long mind", "cognition", "memory_ttl", 2000),
    Affix("bold", "bold", "cognition", "flee_threat", 1.5),
    Affix("craven", "craven", "cognition", "flee_threat", -0.8),
    Affix("curious", "curious", "cognition", "w_explore", 0.6),
    Affix("wary", "wary", "cognition", "threat_radius", 4),
)

BY_KEY: dict[str, Affix] = {affix.key: affix for affix in AFFIX_POOL}

# (name, affix count, relative weight). Deeper ground shifts the weights toward
# the rarer end; see `roll_rarity`.
RARITIES: tuple[tuple[str, int, float], ...] = (
    ("common", 0, 0.55),
    ("uncommon", 1, 0.25),
    ("rare", 2, 0.13),
    ("epic", 3, 0.055),
    ("legendary", 4, 0.015),
)

RARITY_NAMES = tuple(name for name, _, _ in RARITIES)
AFFIX_COUNT = {name: count for name, count, _ in RARITIES}


def roll_rarity(rng: random.Random, depth: float) -> str:
    """Pick a rarity, biased toward the rare end by `depth` (0.0 - 1.0).

    The bias is applied by weighting each tier by (1 + depth) ** index, so at
    the origin the table is its printed self and far out the tail fattens
    without any tier ever becoming impossible.
    """
    weights = [
        weight * (1.0 + depth) ** index
        for index, (_, _, weight) in enumerate(RARITIES)
    ]
    total = sum(weights)
    roll = rng.random() * total
    for (name, _, _), weight in zip(RARITIES, weights):
        roll -= weight
        if roll < 0:
            return name
    return RARITIES[-1][0]


def roll_affixes(rng: random.Random, rarity: str, curse_chance: float) -> tuple[Affix, ...]:
    """Choose this item's affixes: `AFFIX_COUNT[rarity]` of them, no repeats.

    Curses are rolled per affix slot rather than as a separate step, so a
    cursed item always gives something up to carry the curse — which is what
    makes the loadout evaluator's job a real decision.
    """
    count = AFFIX_COUNT[rarity]
    if not count:
        return ()
    blessings = [a for a in AFFIX_POOL if not a.is_curse]
    curses = [a for a in AFFIX_POOL if a.is_curse]
    chosen: list[Affix] = []
    for _ in range(count):
        pool = curses if (curses and rng.random() < curse_chance) else blessings
        options = [a for a in pool if a not in chosen]
        if not options:
            continue
        chosen.append(options[rng.randrange(len(options))])
    return tuple(chosen)


def describe(base_key: str, affixes: tuple[Affix, ...]) -> str:
    """A readable name: 'keen sword of the long mind'."""
    prefixes = [a.label for a in affixes if not a.label.startswith("of ")]
    suffixes = [a.label for a in affixes if a.label.startswith("of ")]
    parts = [*prefixes, base_key, *suffixes]
    return " ".join(parts)
