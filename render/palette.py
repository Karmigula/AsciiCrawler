"""Colour: what the world is made of, and how it changes as you go out.

Ascii does not have to mean grey. The three biome bands read as three
different places when they are lit differently, and because the bands blend by
distance rather than switching, walking outward *looks* like walking outward:
dry warm stone near home, damp cold rock in the caves, and a bruised volcanic
dark in the far caverns.

Two rules keep it from turning into a fruit salad:

- Terrain stays low-saturation. It is the backdrop, and anything that competes
  with the agent, a monster or an item for attention is working against the
  reader.
- Everything that matters is *brighter or warmer* than the ground it stands on,
  never merely a different hue - the fog tiers multiply brightness, so hue
  alone would vanish the moment a tile stopped being visible.

Per-tile jitter is hashed from world position, so a given stone keeps its
shade for the life of the world and the wall does not shimmer as the camera
moves. Everything here is pure and pygame-free.
"""

import math

Color = tuple[int, int, int]
Position = tuple[int, int]

_MASK = (1 << 32) - 1


def _hash01(x: int, y: int, salt: int) -> float:
    """A stable 0..1 value for a world coordinate."""
    h = (x * 0x1F1F1F1F) ^ (y * 0x27220A95) ^ salt
    h &= _MASK
    h ^= h >> 16
    h = (h * 0x7FEB352D) & _MASK
    h ^= h >> 15
    return (h & 0xFFFF) / 0xFFFF


def _lerp(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def _jitter(color: Color, amount: float) -> Color:
    """Scale a colour by `amount`, clamped to a byte."""
    return (
        max(0, min(255, round(color[0] * amount))),
        max(0, min(255, round(color[1] * amount))),
        max(0, min(255, round(color[2] * amount))),
    )


def depth_shade(coord: Position, config) -> float:
    """A brightness factor that falls off with distance from the origin.

    The biome sets the hue now, so depth needs its own signal or every place
    looks equally far from home. Kept small: it should read as "deeper", not
    as "the lights are failing".
    """
    reach = max(1.0, float(config.tier_distance_max))
    far = min(1.0, math.hypot(coord[0], coord[1]) / reach)
    return 1.0 - config.depth_dimming * far


def terrain_color(glyph: str, coord: Position, config, biome_key: str = "halls") -> Color:
    """The unlit colour of one terrain tile, before fog dims it.

    Coloured by which biome the tile is in rather than how far out it is.
    Distance still shows, as a gentle darkening on top.
    """
    table = config.biome_colors.get(biome_key) or config.biome_colors.get("halls", {})
    base = table.get(glyph)
    if base is None:
        return config.floor_color
    spread = config.tile_jitter
    jitter = 1.0 - spread + 2 * spread * _hash01(coord[0], coord[1], 0x5F3A)
    return _jitter(base, jitter * depth_shade(coord, config))


def monster_color(glyph: str, config) -> Color:
    """A monster's colour, by how dangerous it is.

    Deeper things run hotter, so a dragon reads as a dragon before the watcher
    has parsed the letter.
    """
    return config.monster_colors.get(glyph, config.ghost_danger_color)


def item_color(glyph: str, config) -> Color:
    """An item's colour, by what kind of thing it is."""
    return config.item_colors.get(glyph, config.ghost_rare_color)


def background_color(
    glyph: str, coord: Position, tier: str, config, biome_key: str = "halls"
) -> Color | None:
    """The wash behind a cell, or None to leave the window background showing.

    This is what actually carries the biome. A glyph is two lit pixels on a
    black cell, so colouring the punctuation cannot set a mood however careful
    the palette is; colouring the ground can. Kept far darker than the glyph on
    top of it, because the moment the background competes with the foreground
    the grid stops being readable.

    Unknown ground gets nothing: the dark is the point, and washing it would
    hand the watcher the shape of rooms the agent has never seen.
    """
    strength = config.background_strength.get(tier, 0.0)
    if strength <= 0.0:
        return None
    base = terrain_color(glyph, coord, config, biome_key)
    lit = (
        round(base[0] * strength),
        round(base[1] * strength),
        round(base[2] * strength),
    )
    floor = config.background_color
    # Never darker than the window itself, or tiles would read as holes.
    return (max(lit[0], floor[0]), max(lit[1], floor[1]), max(lit[2], floor[2]))


def background_grid(
    rows, origin: Position, visible, known, config, *, tick, ttl, biome_for=None
):
    """The wash for a whole camera window, matching `fog_grid`'s tiers.

    Built from the same `tier_for` the fog uses, so the ground under a tile and
    the glyph on it always agree about how well the agent remembers it.
    """
    from render.fog import tier_for

    age_of = getattr(known, "age", None)
    origin_x, origin_y = origin
    grid = []
    for y, line in enumerate(rows):
        row = []
        for x, glyph in enumerate(line):
            coord = (x + origin_x, y + origin_y)
            tier = tier_for(
                coord,
                visible,
                known,
                tick=tick,
                ttl=ttl,
                stale_fraction=config.memory_stale_fraction,
                age_of=age_of,
            )
            key = "halls" if biome_for is None else biome_for(coord)
            row.append(background_color(glyph, coord, tier, config, key))
        grid.append(row)
    return grid
