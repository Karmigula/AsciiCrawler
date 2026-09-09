from world.tiles import Tile


def test_tile_numeric_codes():
    assert Tile.WALL.value == 0
    assert Tile.FLOOR.value == 1
    assert Tile.WATER.value == 2
    assert Tile.LAVA.value == 3


def test_tile_set_is_exactly_the_four():
    assert [tile.name for tile in Tile] == ["WALL", "FLOOR", "WATER", "LAVA"]


def test_tile_passability():
    assert Tile.FLOOR.passable is True
    assert Tile.WALL.passable is False
    assert Tile.WATER.passable is False
    assert Tile.LAVA.passable is False


def test_tile_glyphs_are_single_characters():
    for tile in Tile:
        assert len(tile.glyph) == 1


def test_tile_glyphs_are_distinct():
    glyphs = [tile.glyph for tile in Tile]
    assert len(set(glyphs)) == len(glyphs)
