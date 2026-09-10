from world.tiles import Tile


def test_tile_numeric_codes():
    assert Tile.WALL.value == 0
    assert Tile.FLOOR.value == 1
    assert Tile.WATER.value == 2
    assert Tile.LAVA.value == 3


def test_the_tile_codes_are_append_only():
    """A saved world is a grid of these numbers, so the existing ones can never
    be reordered - only added to."""
    assert [tile.name for tile in Tile][:4] == ["WALL", "FLOOR", "WATER", "LAVA"]
    assert [tile.value for tile in Tile] == list(range(len(Tile)))


def test_tile_passability():
    assert Tile.FLOOR.passable is True
    assert Tile.WALL.passable is False
    assert Tile.WATER.passable is False
    assert Tile.LAVA.passable is False


def test_the_awkward_tiles_are_passable_but_not_free():
    """Ice and haze can be walked on; the cost is applied by the tick."""
    assert Tile.ICE.passable is True
    assert Tile.ICE.slippery is True
    assert Tile.HAZE.passable is True
    assert Tile.HAZE.harmful is True


def test_ordinary_ground_is_neither_slippery_nor_harmful():
    for tile in (Tile.FLOOR, Tile.WALL, Tile.WATER, Tile.LAVA):
        assert tile.slippery is False
        assert tile.harmful is False


def test_tile_glyphs_are_single_characters():
    for tile in Tile:
        assert len(tile.glyph) == 1


def test_tile_glyphs_are_distinct():
    glyphs = [tile.glyph for tile in Tile]
    assert len(set(glyphs)) == len(glyphs)
