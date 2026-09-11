"""The things down there that have names.

Two sorts, and the difference matters. A **roaming** one is a mini-boss: it
turns up on its own once the creature is big enough to be worth hunting,
walks the world like anything else, and can be met by accident. A **throned**
one sits in a room built for it, one per region at most, and has to be gone
looking for.

Both scale with the creature rather than with the map. A boss whose numbers
were fixed at worldgen is either a wall at level three or furniture at level
twelve; scaling means meeting one is always a fight worth watching, which is
the only thing this game is for.

The table is data, like the biomes and the affixes. Nothing here knows where
anything is - placement belongs to `world/`, and the decision to spawn one
belongs to the tick.
"""

from dataclasses import dataclass, replace

from sim.monsters import MonsterKind


@dataclass(frozen=True)
class BossKind:
    """One named thing, and the shape of the fight it gives you.

    `title` goes after the name - "Vashog, Warden of the Frozen Deep" - so a
    boss reads as somebody rather than as a bigger monster. `throned` ones are
    the room-dwellers; the rest roam.
    """

    key: str
    biome: str
    glyph: str
    title: str
    hp: int
    attack: int
    speed: int
    threat: float
    reach: int = 1
    inflicts: str = ""
    throned: bool = False


# One roamer and one throned boss per biome would be thirty entries and thirty
# names nobody can keep apart. Instead each biome names one of each where it
# earns it, and the rest share the wanderers - which suits a world where the
# same theme covers whole regions.
BOSSES: tuple[BossKind, ...] = (
    # --- roaming: met by accident ---
    BossKind("houndmaster", "halls", "H", "the Houndmaster", 60, 9, 1, 6.0),
    BossKind("tunnelking", "caves", "K", "Tunnel-King", 70, 10, 1, 6.5),
    BossKind("deepmother", "caverns", "M", "the Deep Mother", 90, 12, 2, 7.0),
    BossKind("cinderwake", "ashfields", "F", "Cinderwake", 80, 14, 1, 7.5,
             reach=4, inflicts="weakness"),
    BossKind("bonewright", "ossuary", "B", "the Bonewright", 85, 11, 1, 7.0,
             reach=3, inflicts="frailty"),
    BossKind("sporelord", "warren", "P", "the Spore-Lord", 75, 9, 1, 6.5,
             reach=4, inflicts="blindness"),
    BossKind("greenhusk", "ruins", "G", "Greenhusk", 80, 11, 1, 6.5),
    BossKind("rustsaint", "marsh", "R", "the Rust Saint", 85, 12, 2, 7.0,
             reach=3, inflicts="brittleness"),
    BossKind("prism", "crystal", "Y", "the Prism", 70, 13, 1, 7.0, reach=5),
    BossKind("hoarfrost", "frozen", "Z", "Hoarfrost", 95, 13, 2, 7.5,
             reach=4, inflicts="dread"),
    BossKind("bloomtyrant", "spores", "L", "the Bloom Tyrant", 80, 10, 1, 6.5,
             reach=4, inflicts="blindness"),
    BossKind("drowned", "sunken", "N", "the Drowned Choir", 90, 12, 2, 7.0,
             reach=4),
    BossKind("overseer", "station", "V", "the Overseer", 85, 12, 1, 7.0,
             reach=5, inflicts="weakness"),
    BossKind("enginehead", "machine", "E", "Enginehead", 100, 14, 2, 7.5,
             reach=3),
    BossKind("loomwarden", "weave", "U", "the Loom-Warden", 90, 13, 1, 7.5,
             reach=5, inflicts="dread"),
    # --- throned: sat in a room, waiting ---
    BossKind("crownless", "halls", "A", "the Crownless", 160, 16, 1, 9.0,
             reach=2, throned=True),
    BossKind("stonemother", "caverns", "Q", "the Stone Mother", 200, 18, 2, 9.5,
             reach=3, inflicts="frailty", throned=True),
    BossKind("ashking", "ashfields", "X", "the Ash King", 190, 20, 1, 10.0,
             reach=5, inflicts="weakness", throned=True),
    BossKind("ossuarch", "ossuary", "J", "the Ossuarch", 180, 17, 1, 9.5,
             reach=4, inflicts="frailty", throned=True),
    BossKind("winterjaw", "frozen", "I", "Winterjaw", 210, 19, 2, 10.0,
             reach=4, inflicts="dread", throned=True),
    BossKind("thefirst", "machine", "0", "the First Engine", 220, 21, 2, 10.5,
             reach=4, inflicts="brittleness", throned=True),
)

ROAMERS = tuple(boss for boss in BOSSES if not boss.throned)
THRONED = tuple(boss for boss in BOSSES if boss.throned)
GLYPHS = frozenset(boss.glyph for boss in BOSSES)


def for_biome(biome_key: str, throned: bool):
    """The boss this biome puts up, or None if it does not have that sort."""
    for boss in BOSSES:
        if boss.biome == biome_key and boss.throned == throned:
            return boss
    return None


def roamer_for(biome_key: str):
    """A wandering one for this biome, falling back to any of them.

    Every biome has a roamer today, but the fallback means adding a biome
    without one gets a wanderer rather than silence.
    """
    found = for_biome(biome_key, throned=False)
    return found if found is not None else ROAMERS[0]


def scaled(boss: BossKind, level: int, config) -> MonsterKind:
    """A `MonsterKind` for this boss at the creature's current level.

    Everything else in the world is placed once and keeps its numbers, which
    is right for a rat. For something with a name it would mean the fight is
    decided by when it spawned rather than by how it goes, so a boss is built
    fresh at the level it is met.
    """
    step = max(0, level - 1) * config.boss_scale_per_level
    return MonsterKind(
        key=boss.key,
        glyph=boss.glyph,
        hp=int(boss.hp * (1.0 + step)),
        attack=int(round(boss.attack * (1.0 + step * 0.6))),
        speed=boss.speed,
        threat=boss.threat,
        tier=5,
        reach=boss.reach,
        inflicts=boss.inflicts,
        inflict_chance=0.3,
    )
