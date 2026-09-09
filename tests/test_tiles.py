from world.tiles import Tile


def test_tile_numeric_codes():
    assert Tile.WALL.value == 0
    assert Tile.FLOOR.value == 1


def test_tile_passability():
    assert Tile.FLOOR.passable is True
    assert Tile.WALL.passable is False


def test_tile_glyphs_are_single_characters():
    for tile in Tile:
        assert len(tile.glyph) == 1
