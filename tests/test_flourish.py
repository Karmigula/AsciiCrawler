"""Phase 7 flourishes: the chronicle, moss, and the two lava behaviours."""

import random

from config import DEFAULT_CONFIG
from dataclasses import replace
from render.flourish import speckle_moss
from sim.chronicle import Chronicle, found, killed, levelled
from sim.monsters import MONSTERS
from world.populate import Item, Monster
from world.tiles import Tile

WHITE = (200, 200, 200)
FLOOR_GLYPH = Tile.FLOOR.glyph


def _grid(width=20, height=20, glyph=FLOOR_GLYPH):
    return [[(glyph, WHITE) for _ in range(width)] for _ in range(height)]


# --- chronicle -------------------------------------------------------------


def test_the_chronicle_keeps_only_the_recent_past():
    """An unbounded log in a process meant to run for days is a leak."""
    log = Chronicle(limit=4)
    for i in range(50):
        log.record(i, f"thing {i}")
    assert len(log) == 4
    assert log.total == 50
    assert log.recent()[-1] == (49, "thing 49")
    assert log.recent()[0] == (46, "thing 46")


def test_the_chronicle_reads_oldest_first():
    log = Chronicle(limit=8)
    log.record(1, "first")
    log.record(2, "second")
    assert [text for _, text in log.recent()] == ["first", "second"]


def test_recent_can_be_narrowed():
    log = Chronicle(limit=8)
    for i in range(5):
        log.record(i, str(i))
    assert len(log.recent(2)) == 2


def test_the_phrasing_says_what_happened():
    kind = next(k for k in MONSTERS if k.glyph == "T")
    monster = Monster(kind=kind, x=0, y=0, hp=kind.hp)
    assert "troll" in killed(monster)
    assert "level 4" in levelled(4)

    from sim.affixes import BY_KEY
    from sim.items import ITEMS

    kinds = {k.key: k for k in ITEMS}
    plain = Item(kind=kinds["armor"], x=0, y=0)
    fancy = Item(
        kind=kinds["weapon"], x=0, y=0, rarity="rare", affixes=(BY_KEY["cruel"],)
    )
    assert "plain armor" in found(plain)
    assert "cruel weapon" in found(fancy)


# --- moss ------------------------------------------------------------------


def test_moss_is_stable_for_a_given_tile():
    """Decorative, but it must not shimmer as the camera moves."""
    first = speckle_moss(_grid(), (100, 100), FLOOR_GLYPH, DEFAULT_CONFIG)
    second = speckle_moss(_grid(), (100, 100), FLOOR_GLYPH, DEFAULT_CONFIG)
    assert first == second
    # The same world tile, reached at a different grid offset, keeps its look.
    shifted = speckle_moss(_grid(), (101, 100), FLOOR_GLYPH, DEFAULT_CONFIG)
    assert first[0][1] == shifted[0][0]


def test_moss_only_lands_on_floor():
    grid = _grid(glyph="#")
    assert speckle_moss(grid, (0, 0), FLOOR_GLYPH, DEFAULT_CONFIG) == grid


def test_moss_leaves_blank_cells_alone():
    grid = _grid()
    grid[0][0] = None
    out = speckle_moss(grid, (0, 0), FLOOR_GLYPH, DEFAULT_CONFIG)
    assert out[0][0] is None


def test_some_tiles_are_mossy_and_most_are_not():
    out = speckle_moss(_grid(40, 40), (0, 0), FLOOR_GLYPH, DEFAULT_CONFIG)
    tinted = sum(1 for row in out for cell in row if cell[1] != WHITE)
    total = 40 * 40
    assert 0 < tinted < total * 0.25


def test_moss_can_be_switched_off():
    config = replace(DEFAULT_CONFIG, moss_chance=0.0)
    grid = _grid()
    assert speckle_moss(grid, (0, 0), FLOOR_GLYPH, config) == grid
