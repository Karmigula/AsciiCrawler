"""What everything on screen actually is.

One table, read by the desktop window and by the browser, because two tables
would eventually disagree and the whole point of a cheat sheet is that it can
be trusted. Rows are built from the same registries the game draws from - the
tile enum, the monster table, the item table - so a glyph that exists and is
missing here is a bug this module can be asked about rather than a gap nobody
notices.

Colours come with the rows: a legend printed in one colour is a worse legend,
since half of what a glyph tells you at a glance is what shade it is.
"""

from config import Config
from sim.items import GRAVE, ITEMS
from sim.monsters import MONSTERS
from world.tiles import Tile

SHRINE_GLYPH = "&"

Row = tuple[str, str, tuple[int, int, int]]


def _tile_rows(config: Config) -> list[Row]:
    """Ground, in the order a reader meets it."""
    from render.palette import terrain_color

    described = {
        Tile.WALL: "rock - you cannot go through it",
        Tile.FLOOR: "floor - you can",
        Tile.WATER: "water - too deep to cross",
        Tile.LAVA: "lava - deep and hot",
        Tile.ICE: "ice - it keeps you moving",
        Tile.HAZE: "fog - walkable, and it hurts",
    }
    return [
        (tile.glyph, described[tile], terrain_color(tile.glyph, (0, 0), config))
        for tile in Tile
    ]


def _monster_rows(config: Config) -> list[Row]:
    """Everything that fights back, weakest first."""
    from render.palette import monster_color

    return [
        (kind.glyph, f"{kind.key} - {kind.hp} hp", monster_color(kind.glyph, config))
        for kind in sorted(MONSTERS, key=lambda kind: (kind.tier, kind.hp))
    ]


def _item_rows(config: Config) -> list[Row]:
    """Loot, and the two things on the floor that are not loot."""
    from render.palette import item_color

    described = {
        "weapon": "a weapon",
        "armor": "armour",
        "ring": "a ring",
        "amulet": "an amulet",
        "potion": "a potion - drunk when hurt",
        "gold": "gold",
    }
    rows = [
        (kind.glyph, described.get(kind.key, kind.key), item_color(kind.glyph, config))
        for kind in ITEMS
    ]
    rows.append((GRAVE.glyph, "a grave - somebody died here", item_color(GRAVE.glyph, config)))
    rows.append((SHRINE_GLYPH, "a totem - blesses or curses, once", config.shrine_color))
    return rows


def _boss_rows(config: Config) -> list[Row]:
    """The named things, roamers first.

    Listed by what sort of thing they are rather than by name, because the
    name is rolled per creature: the sheet can say a Z is Hoarfrost and that
    Hoarfrost hunts the frozen deep, but not what it will be called.
    """
    from sim.bosses import BOSSES

    return [
        (
            boss.glyph,
            f"{boss.title} - {'waits in a room' if boss.throned else 'roams'}",
            config.boss_color,
        )
        for boss in sorted(BOSSES, key=lambda b: (b.throned, b.title))
    ]


def legend_sections(config: Config) -> list[tuple[str, list[Row]]]:
    """The whole sheet: (heading, rows) in reading order."""
    return [
        ("the creature", [("@", "the creature - nobody is steering it", config.agent_color)]),
        ("ground", _tile_rows(config)),
        ("things", _item_rows(config)),
        ("company", _monster_rows(config)),
        ("the named", _boss_rows(config)),
    ]


def legend_lines(config: Config) -> list[tuple[str, tuple[int, int, int]]]:
    """The sheet as (text, colour) lines, for the desktop screen."""
    from render.menu import block_text

    lines: list[tuple[str, tuple[int, int, int]]] = [
        (row, config.menu_title_color) for row in block_text("LEGEND")
    ]
    for heading, rows in legend_sections(config):
        lines.append(("", config.menu_dim_color))
        lines.append((heading, config.menu_dim_color))
        for glyph, text, colour in rows:
            lines.append((f"  {glyph}   {text}", colour))
    lines.append(("", config.menu_dim_color))
    lines.append(("j or esc to go back", config.menu_dim_color))
    return lines
