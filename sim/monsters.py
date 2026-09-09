"""The monster table — data only. Behaviour, combat and death are Phase 4.

Tiers are the depth dial: a chunk's distance from the world origin decides
the deepest tier its table may roll, so rats live everywhere and dragons only
in the far dark. Stats are deliberately plain; the affix system (Phase 5)
decorates items, not monsters.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MonsterKind:
    """One species. `speed` is ticks-per-move for the Phase 4 scheduler;
    `threat` is the FLEE weight the Phase 4 brain will read."""

    key: str
    glyph: str
    hp: int
    attack: int
    speed: int
    threat: float
    tier: int


MONSTERS: tuple[MonsterKind, ...] = (
    MonsterKind("rat", "r", hp=3, attack=1, speed=1, threat=0.5, tier=0),
    MonsterKind("goblin", "g", hp=7, attack=2, speed=1, threat=1.0, tier=1),
    MonsterKind("orc", "o", hp=14, attack=4, speed=1, threat=2.0, tier=2),
    MonsterKind("ogre", "O", hp=26, attack=7, speed=2, threat=3.5, tier=3),
    MonsterKind("troll", "T", hp=40, attack=10, speed=2, threat=5.0, tier=4),
    MonsterKind("dragon", "D", hp=80, attack=18, speed=1, threat=9.0, tier=5),
)

MAX_TIER = max(kind.tier for kind in MONSTERS)


def table_for_tier(max_tier: int) -> tuple[MonsterKind, ...]:
    """Every kind up to `max_tier` — the roll table at a given depth."""
    return tuple(kind for kind in MONSTERS if kind.tier <= max_tier)
