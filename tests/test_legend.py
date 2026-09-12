"""The cheat sheet, and the promise that it is complete."""

from config import DEFAULT_CONFIG
from render.legend import legend_sections


def _bolt_glyphs():
    from sim.spells import BOLT_GLYPHS

    return set(BOLT_GLYPHS.values())


def _boss_glyphs():
    from sim.bosses import BOSSES

    return {boss.glyph for boss in BOSSES}


def _glyphs():
    return {glyph for _, rows in legend_sections(DEFAULT_CONFIG) for glyph, _, _ in rows}


def test_the_sheet_explains_everything_that_can_be_on_screen():
    """A legend with a gap in it is worse than no legend.

    Built from the same registries the game draws from, so this catches the
    real failure: somebody adds a monster or a tile and the sheet quietly
    stops being the whole truth.
    """
    from sim.items import GRAVE, ITEMS
    from sim.monsters import MONSTERS
    from world.tiles import Tile

    drawable = (
        {tile.glyph for tile in Tile}
        | {kind.glyph for kind in MONSTERS}
        | {kind.glyph for kind in ITEMS}
        | {GRAVE.glyph, "&", "%", DEFAULT_CONFIG.agent_glyph}
        | _boss_glyphs()
        | _bolt_glyphs()
    )

    missing = sorted(drawable - _glyphs())

    assert not missing, f"the legend does not explain {missing}"


def test_the_sheet_explains_nothing_that_is_not_real():
    """The other direction: a row for something the game never draws."""
    from sim.items import GRAVE, ITEMS
    from sim.monsters import MONSTERS
    from world.tiles import Tile

    drawable = (
        {tile.glyph for tile in Tile}
        | {kind.glyph for kind in MONSTERS}
        | {kind.glyph for kind in ITEMS}
        | {GRAVE.glyph, "&", "%", DEFAULT_CONFIG.agent_glyph}
        | _boss_glyphs()
        | _bolt_glyphs()
    )

    invented = sorted(_glyphs() - drawable)

    assert not invented, f"the legend describes {invented}, which nothing draws"


def test_every_row_says_something():
    for heading, rows in legend_sections(DEFAULT_CONFIG):
        assert heading.strip()
        assert rows, f"{heading} is empty"
        for glyph, text, colour in rows:
            assert len(glyph) == 1, f"{glyph!r} is not one character"
            assert text.strip(), f"{glyph} has no explanation"
            assert len(colour) == 3, f"{glyph} has no colour"


def test_the_flat_sheet_holds_everything_the_sections_do():
    from render.legend import legend_rows

    entries = [row for kind, row in legend_rows(DEFAULT_CONFIG) if kind == "row"]
    from_sections = [row for _heading, rows in legend_sections(DEFAULT_CONFIG) for row in rows]

    assert entries == from_sections


def test_columns_never_hold_more_rows_than_they_were_given_room_for():
    """The reported bug was the sheet running off the bottom of the window.

    `draw_centered` does not clip, so at fifty-one entries a single column
    simply carried on past the edge and the last third of the bestiary was not
    on screen at all.
    """
    from render.legend import columns_for, legend_rows

    rows = legend_rows(DEFAULT_CONFIG)
    for room in (4, 9, 17, 24, 60, 500):
        for column in columns_for(rows, room):
            assert len(column) <= room, f"a column held {len(column)} with room for {room}"


def test_no_row_is_lost_when_the_sheet_is_split():
    from render.legend import columns_for, legend_rows

    rows = legend_rows(DEFAULT_CONFIG)
    for room in (5, 12, 30):
        kept = [row for column in columns_for(rows, room) for row in column]
        assert [r for r in kept if r[0] != "gap"] == [r for r in rows if r[0] != "gap"]


def test_a_heading_is_never_left_at_the_foot_of_a_column():
    """A heading with nothing under it is worse than a short column."""
    from render.legend import columns_for, legend_rows

    rows = legend_rows(DEFAULT_CONFIG)
    for room in (6, 11, 19, 28):
        for column in columns_for(rows, room):
            if column and column[-1][0] == "heading":
                raise AssertionError(f"a heading was stranded with room={room}")
