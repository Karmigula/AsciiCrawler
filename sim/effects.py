"""Blessings and curses: things that are true of the creature for a while.

Gear changes what the agent *is* and is chosen deliberately; an effect happens
*to* it and wears off. That difference is the whole design here. Effects are
held as {key: ticks left} on the agent, counted down once a tick, and folded
into the derived numbers the same way equipment is - so a cursed creature
plans with the sight it actually has, not the sight it wishes it had.

Nothing in here reaches for the world or the agent. An effect is a name, a
duration and a handful of modifiers, which keeps the table readable and lets a
test hand the evaluator whatever it likes.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EffectKind:
    """One blessing or curse.

    The modifiers are added to the derived stats after gear, so a curse can
    take away what a good sword gave. `flee_threat` and `w_explore` move the
    temperament rather than the body: dread makes it skittish, resolve makes
    it bold, and both read as a change of mind from the outside.
    """

    key: str
    label: str
    blessing: bool
    ticks: int
    attack: int = 0
    defense: int = 0
    max_hp: int = 0
    max_mp: int = 0
    fov_radius: int = 0
    flee_threat: float = 0.0
    w_explore: float = 0.0


EFFECTS: tuple[EffectKind, ...] = (
    # Blessings
    EffectKind("might", "might", True, 900, attack=3),
    EffectKind("warding", "warding", True, 900, defense=3),
    EffectKind("vigour", "vigour", True, 1200, max_hp=12),
    EffectKind("farsight", "farsight", True, 1200, fov_radius=3),
    EffectKind("resolve", "resolve", True, 900, flee_threat=0.5, w_explore=0.4),
    EffectKind("wellspring", "wellspring", True, 1000, max_mp=10),
    # Curses
    EffectKind("weakness", "weakness", False, 700, attack=-2),
    EffectKind("brittleness", "brittleness", False, 700, defense=-2),
    EffectKind("blindness", "dimness", False, 600, fov_radius=-3),
    EffectKind("dread", "dread", False, 700, flee_threat=-0.4, w_explore=-0.3),
    EffectKind("frailty", "frailty", False, 800, max_hp=-8),
    EffectKind("dampening", "dampening", False, 700, max_mp=-8),
)

BY_KEY = {effect.key: effect for effect in EFFECTS}
BLESSINGS = tuple(effect.key for effect in EFFECTS if effect.blessing)
CURSES = tuple(effect.key for effect in EFFECTS if not effect.blessing)


def apply(active: dict, key: str) -> dict:
    """Start an effect, or reset one already running back to full.

    Refreshing rather than stacking: two blessings of might should be a
    longer blessing, not a creature with six more attack than it can survive
    losing. The same rule keeps a cursed agent from being buried by a row of
    effigies it walked past.
    """
    kind = BY_KEY.get(key)
    if kind is None:
        return active
    active[key] = kind.ticks
    return active


def tick(active: dict) -> list[str]:
    """Count every effect down one tick; return whatever just ran out."""
    expired = []
    for key in list(active):
        active[key] -= 1
        if active[key] <= 0:
            del active[key]
            expired.append(key)
    return expired


def modifiers(active) -> dict:
    """What the currently-running effects add up to."""
    totals = {
        "attack": 0,
        "defense": 0,
        "max_hp": 0,
        "max_mp": 0,
        "fov_radius": 0,
        "flee_threat": 0.0,
        "w_explore": 0.0,
    }
    for key in active:
        kind = BY_KEY.get(key)
        if kind is None:
            continue
        for field_name in totals:
            totals[field_name] += getattr(kind, field_name)
    return totals


def describe(active) -> list[tuple[str, bool, int]]:
    """(label, blessing, ticks left) for each effect, blessings first."""
    rows = []
    for key, left in active.items():
        kind = BY_KEY.get(key)
        if kind is not None:
            rows.append((kind.label, kind.blessing, left))
    rows.sort(key=lambda row: (not row[1], row[0]))
    return rows
