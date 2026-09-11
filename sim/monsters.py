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
    # How far it can hit from. One means it has to be standing next to you,
    # which is what everything in the game did before spells existed.
    reach: int = 1
    # A status effect it may leave on the agent when it lands a blow.
    inflicts: str = ""
    inflict_chance: float = 0.25


MONSTERS: tuple[MonsterKind, ...] = (
    MonsterKind("rat", "r", hp=3, attack=1, speed=1, threat=0.5, tier=0),
    MonsterKind("goblin", "g", hp=7, attack=2, speed=1, threat=1.0, tier=1),
    MonsterKind("orc", "o", hp=14, attack=4, speed=1, threat=2.0, tier=2),
    MonsterKind("ogre", "O", hp=26, attack=7, speed=2, threat=3.5, tier=3),
    MonsterKind("troll", "T", hp=40, attack=10, speed=2, threat=5.0, tier=4),
    MonsterKind("dragon", "D", hp=80, attack=18, speed=1, threat=9.0, tier=5),
    # Constructs: the bestiary of the built places. Tiered alongside the
    # beasts rather than above them, so a shallow station is a nuisance and a
    # deep one is not.
    MonsterKind("mite", "x", hp=4, attack=1, speed=1, threat=0.6, tier=0),
    MonsterKind("sentry", "S", hp=16, attack=5, speed=2, threat=2.4, tier=2),
    MonsterKind("construct", "C", hp=30, attack=8, speed=2, threat=4.0, tier=3),
    MonsterKind("warden", "W", hp=70, attack=16, speed=1, threat=8.0, tier=5),
)

MAX_TIER = max(kind.tier for kind in MONSTERS)

BY_GLYPH: dict[str, MonsterKind] = {kind.glyph: kind for kind in MONSTERS}
"""Glyph -> kind. The agent remembers glyphs, not objects, so this is how the
brain prices what it saw: memory holds a snapshot, never a monster."""


def table_for_tier(max_tier: int) -> tuple[MonsterKind, ...]:
    """Every kind up to `max_tier` — the roll table at a given depth."""
    return tuple(kind for kind in MONSTERS if kind.tier <= max_tier)


# What a spell can leave on a monster. Small, and the point of them is that a
# creature far weaker than a boss can still make the fight winnable: chilled
# things act less often, withered things hit softer.
MONSTER_EFFECTS = {
    "chilled": {"label": "chilled", "slow": 1, "ticks": 60},
    "withered": {"label": "withered", "attack": -3, "ticks": 80},
}


def afflict(monster, key: str) -> None:
    """Start (or refresh) an effect on a monster."""
    rule = MONSTER_EFFECTS.get(key)
    if rule is None:
        return
    monster.effects[key] = rule["ticks"]


def effective_speed(monster) -> int:
    """Ticks between this monster's moves, with anything chilling it."""
    slow = sum(
        MONSTER_EFFECTS[key].get("slow", 0)
        for key in monster.effects
        if key in MONSTER_EFFECTS
    )
    return max(1, monster.kind.speed + slow)


def effective_attack(monster) -> int:
    """What it hits for, with anything withering it."""
    change = sum(
        MONSTER_EFFECTS[key].get("attack", 0)
        for key in monster.effects
        if key in MONSTER_EFFECTS
    )
    return max(1, monster.kind.attack + change)


def fade(monster) -> None:
    """Count a monster's effects down one tick."""
    for key in list(monster.effects):
        monster.effects[key] -= 1
        if monster.effects[key] <= 0:
            del monster.effects[key]
