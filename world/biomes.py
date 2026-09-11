"""What kind of place a chunk is, and where those places are.

Two independent dials, which is the point of doing it this way:

- *Distance* from the origin still decides how dangerous and how rich a chunk
  is - monster tier, spawn density, loot rarity. That gradient is unchanged.
- *Region noise* decides what the place looks and behaves like. Themes form
  patches several chunks across that the agent wanders between, so a frozen
  hollow can sit next to quarried halls and either can turn up at any depth.

Before this, biome was a function of distance alone: three of them, in rings.
Three fit on a line; twelve do not, and rings would have meant never seeing
most of them without walking for an hour.

A biome is data. It names a generator and its parameters, a palette, which
monsters belong there, and what liquids it may contain. Adding one should be
an entry in this table and nothing else - if it ever needs code, the table is
missing a dial.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Biome:
    """One kind of place."""

    key: str
    label: str
    builder: str  # which generator: see world.chunks._BUILDERS
    params: dict = field(default_factory=dict)  # generator overrides
    monsters: tuple[str, ...] = ()  # glyphs allowed here; empty means all
    # What this biome puts up to be worshipped, and how kindly it answers.
    # `shrine` empty means the place has nothing of the sort.
    shrine: str = ""
    shrine_glyph: str = "&"  # ascii on purpose: the cheat sheet has to name it
    blessing_chance: float = 0.6
    # What this biome's builder can actually produce. Only the cavern builder
    # grows pools, so a biome that wants water has to use it - the field
    # describes the terrain, it does not request it.
    liquids: str = "none"
    weight: float = 1.0  # how often this theme comes up

    @property
    def has_water(self) -> bool:
        return self.liquids in ("water", "both")

    @property
    def has_lava(self) -> bool:
        return self.liquids in ("lava", "both")


# The table. Palettes live in config.biome_colors under the same keys, because
# colour is a thing to tune by eye and belongs with the other tunables.
BIOMES: tuple[Biome, ...] = (
    Biome(
        "halls",
        "quarried halls",
        builder="rooms",
        params={"min_partition": 12, "min_room": 4},
        monsters=("r", "g", "o", "O"),
        weight=1.2,
        shrine="a mason's mark",
        blessing_chance=0.65,
    ),
    Biome(
        "caves",
        "wet caves",
        builder="cave",
        params={"fill_prob": 0.45, "smooth_steps": 4},
        monsters=("r", "g", "o", "O", "T"),
        weight=1.2,
        shrine="a cairn",
        blessing_chance=0.6,
    ),
    Biome(
        "caverns",
        "deep caverns",
        builder="cavern",
        params={"fill_prob": 0.42, "smooth_steps": 5},
        liquids="both",
        weight=1.0,
        shrine="a dripping idol",
        blessing_chance=0.55,
    ),
    Biome(
        "ashfields",
        "the ashfields",
        builder="cavern",
        # Wide open and full of lava: the pools are the terrain here, not a
        # feature of it.
        params={
            "fill_prob": 0.38,
            "smooth_steps": 5,
            "pool_chance": 0.95,
            "pool_attempts": 9,
            "pool_min_size": 14,
            "pool_max_size": 70,
            "lava_share": 0.92,
        },
        monsters=("o", "O", "T", "D"),
        liquids="lava",
        weight=0.7,
        shrine="a scorched effigy",
        blessing_chance=0.4,
    ),
    Biome(
        "ossuary",
        "the ossuary",
        builder="rooms",
        # Many small chambers rather than a few large ones: niches, not halls.
        params={"min_partition": 7, "min_room": 2},
        monsters=("r", "g", "T"),
        weight=0.8,
        shrine="a bone pillar",
        blessing_chance=0.3,
    ),
    Biome(
        "warren",
        "fungal warren",
        builder="cavern",
        # Low fill and heavy smoothing rounds the walls into bulbs; shallow
        # standing water between them, never lava.
        params={
            "fill_prob": 0.40,
            "smooth_steps": 6,
            "pool_chance": 0.7,
            "pool_attempts": 5,
            "pool_min_size": 6,
            "pool_max_size": 24,
            "lava_share": 0.0,
        },
        monsters=("r", "g", "o"),
        liquids="water",
        weight=0.9,
        shrine="a fruiting totem",
        blessing_chance=0.6,
    ),
    Biome(
        "ruins",
        "overgrown ruins",
        builder="ruins",  # rooms first, then let the cave eat them
        params={"min_partition": 11, "min_room": 3, "fill_prob": 0.44, "smooth_steps": 3},
        monsters=("r", "g", "o", "T"),
        weight=1.0,
        shrine="a toppled saint",
        blessing_chance=0.6,
    ),
    Biome(
        "marsh",
        "rust marsh",
        builder="cavern",
        params={
            "fill_prob": 0.44,
            "smooth_steps": 4,
            "pool_chance": 0.9,
            "pool_attempts": 8,
            "pool_min_size": 12,
            "pool_max_size": 60,
            "lava_share": 0.0,
        },
        monsters=("r", "g", "o", "O"),
        liquids="water",
        weight=0.9,
        shrine="a rusted shrine",
        blessing_chance=0.45,
    ),
    Biome(
        "crystal",
        "crystal hollows",
        builder="cave",
        # Very heavy smoothing gives long clean faces instead of ragged rock.
        params={"fill_prob": 0.47, "smooth_steps": 8},
        monsters=("g", "o", "O", "T", "D"),
        weight=0.6,
        shrine="a singing shard",
        blessing_chance=0.7,
    ),
    Biome(
        "frozen",
        "the frozen deep",
        builder="cave",
        # Open rock, then drifts of ice settled over the floor.
        params={
            "fill_prob": 0.43,
            "smooth_steps": 5,
            "scatter": {"tile": "ICE", "chance": 0.46, "smooth_steps": 3},
        },
        monsters=("r", "g", "o", "T", "D"),
        weight=0.8,
        shrine="a rimed effigy",
        blessing_chance=0.45,
    ),
    Biome(
        "spores",
        "spore hollows",
        builder="cave",
        params={
            "fill_prob": 0.41,
            "smooth_steps": 5,
            "scatter": {"tile": "HAZE", "chance": 0.40, "smooth_steps": 3},
        },
        monsters=("r", "g", "o", "O"),
        weight=0.7,
        shrine="a spore-caked totem",
        blessing_chance=0.4,
    ),
    Biome(
        "sunken",
        "the sunken cathedral",
        builder="causeway",
        params={"causeways": 3, "platform_chance": 0.65},
        monsters=("r", "g", "o", "T"),
        liquids="water",
        weight=0.6,
        shrine="a drowned altar",
        blessing_chance=0.5,
    ),
    Biome(
        "station",
        "derelict station",
        builder="station",
        params={"cell": 11, "door_chance": 0.62, "sealed_chance": 0.16},
        monsters=("x", "S", "C", "W"),
        weight=0.9,
        shrine="a dead terminal",
        blessing_chance=0.55,
    ),
    Biome(
        "machine",
        "machine halls",
        builder="maze",
        params={"braid": 0.3},
        monsters=("x", "S", "C", "W"),
        weight=0.6,
        shrine="a humming pillar",
        blessing_chance=0.5,
    ),
    Biome(
        "weave",
        "the weave",
        builder="lattice",
        params={"period": 6, "gap_chance": 0.3},
        monsters=("x", "S", "C", "W", "D"),
        weight=0.5,
        shrine="a knot in the weave",
        blessing_chance=0.5,
    ),
)

BY_KEY: dict[str, Biome] = {biome.key: biome for biome in BIOMES}
DEFAULT = BIOMES[0]

_MASK64 = (1 << 64) - 1
_REGION_SALT = 0xB10E5
_THRONE_SALT = 0x7480E5
_SPOT_SALT = 0x5E4757


def _mix(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & _MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK64
    return value ^ (value >> 31)


def region_of(cx: int, cy: int, region_size: int) -> tuple[int, int]:
    """Which region cell a chunk belongs to. Works for negative coordinates."""
    size = max(1, region_size)
    return cx // size, cy // size


def biome_at(seed: int, cx: int, cy: int, config) -> Biome:
    """The biome for a chunk, from its region rather than its distance.

    Deterministic in (seed, region), so a theme covers a whole patch and the
    same world always grows the same places. Nothing here looks at distance:
    danger and loot scale with that separately, which is what lets a low-level
    creature meet the crystal hollows and a veteran still walk quarried halls.
    """
    region_x, region_y = region_of(cx, cy, config.region_size)
    roll = _mix(_mix(seed ^ _REGION_SALT) ^ _mix((region_x << 32) ^ (region_y & 0xFFFFFFFF)))
    total = sum(biome.weight for biome in BIOMES)
    point = (roll % 100_000) / 100_000 * total
    for biome in BIOMES:
        point -= biome.weight
        if point < 0:
            return biome
    return BIOMES[-1]


def throne_chunk(seed: int, cx: int, cy: int, config) -> bool:
    """Whether this chunk is the one its region built a boss room in.

    One per region at most, decided from the seed and the region alone, so a
    throne is in the same place every time the world is grown and nothing has
    to be remembered between sessions. Regions near the origin are left empty:
    the first thing a new creature meets should not have a name.
    """
    size = max(1, config.region_size)
    region = region_of(cx, cy, size)
    if max(abs(region[0]), abs(region[1])) <= config.boss_room_free_radius:
        return False
    # Mixed the same way the biome roll is, with its own salt so the two
    # decisions cannot correlate: a region should not be likelier to hold a
    # throne for having come out as the ashfields.
    stamp = _mix((region[0] << 32) ^ (region[1] & 0xFFFFFFFF))
    roll = _mix(_mix(seed ^ _THRONE_SALT) ^ stamp)
    if (roll % 100_000) / 100_000 >= config.boss_room_chance:
        return False
    # Which chunk of the region gets it, from its own draw.
    spot = _mix(_mix(seed ^ _SPOT_SALT) ^ stamp) % (size * size)
    return (cx - region[0] * size, cy - region[1] * size) == (spot % size, spot // size)
