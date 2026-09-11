"""The cheat sheet, and the promise that it is complete."""

from config import DEFAULT_CONFIG
from render.legend import legend_lines, legend_sections


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
        | {GRAVE.glyph, "&", DEFAULT_CONFIG.agent_glyph}
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
        | {GRAVE.glyph, "&", DEFAULT_CONFIG.agent_glyph}
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


def test_the_desktop_sheet_says_how_to_leave_it():
    text = "\n".join(line for line, _ in legend_lines(DEFAULT_CONFIG))

    assert "j" in text and "esc" in text
    assert "rock" in text and "totem" in text
