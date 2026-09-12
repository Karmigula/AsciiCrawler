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
SHOP_GLYPH = "%"

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
    rows.append((SHOP_GLYPH, "a stall - three things, for gold", config.shop_color))
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


def _bolt_rows(config: Config) -> list[Row]:
    """The marks a spell leaves crossing the room.

    They last a few ticks and are gone, which is exactly why they need a line
    on the sheet: a glyph you see for a quarter of a second and never again is
    the hardest kind to look up.
    """
    from sim.spells import SPELLS

    colour = config.spell_colors.get("ember_bolt", (250, 148, 60))
    return [
        ("-", "a spell in flight", colour),
        ("|", "the same, going the other way", colour),
        ("/", "and on the diagonal", colour),
        ("\\", "and the other diagonal", colour),
    ]


def legend_sections(config: Config) -> list[tuple[str, list[Row]]]:
    """The whole sheet: (heading, rows) in reading order."""
    return [
        ("the creature", [("@", "the creature - nobody is steering it", config.agent_color)]),
        ("ground", _tile_rows(config)),
        ("things", _item_rows(config)),
        ("company", _monster_rows(config)),
        ("spells", _bolt_rows(config)),
        ("the named", _boss_rows(config)),
    ]


def legend_rows(config: Config) -> list:
    """The sheet flattened to one list: ("heading", text) or ("row", entry).

    Flat because the screen lays it out in columns and a column break has to
    be allowed to fall anywhere - a nested shape would force every section to
    start a new column, and with six sections and fifty-one entries that wastes
    most of the window.
    """
    rows: list = []
    for heading, entries in legend_sections(config):
        rows.append(("heading", heading))
        rows.extend(("row", entry) for entry in entries)
        rows.append(("gap", None))
    return rows[:-1] if rows else rows


def columns_for(rows: list, per_column: int) -> list:
    """Split the flat list into columns of at most `per_column` rows.

    A heading is never left stranded at the foot of a column: if one would be,
    the column ends early and it starts the next. A heading with nothing under
    it is worse than a short column.
    """
    per_column = max(1, per_column)
    columns: list = [[]]
    for index, row in enumerate(rows):
        current = columns[-1]
        stranded = (
            len(current) >= per_column - 1
            and row[0] == "heading"
            and index + 1 < len(rows)
        )
        if current and (len(current) >= per_column or stranded):
            columns.append([])
            current = columns[-1]
        if row[0] == "gap" and not current:
            continue  # no blank line at the top of a column
        current.append(row)
    return columns
