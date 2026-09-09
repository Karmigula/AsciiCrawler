from world.hardcoded import Tile, build_map


def test_build_map_dimensions():
    tiles = build_map(96, 54)
    assert len(tiles) == 54
    assert all(len(row) == 96 for row in tiles)


def test_build_map_has_wall_border_and_floor_interior():
    tiles = build_map(96, 54)
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            on_border = x in (0, 95) or y in (0, 53)
            assert tile is (Tile.WALL if on_border else Tile.FLOOR), (x, y)


def test_build_map_all_walls_when_no_interior():
    tiles = build_map(2, 2)
    assert all(tile is Tile.WALL for row in tiles for tile in row)


def test_tile_passability():
    assert Tile.FLOOR.passable is True
    assert Tile.WALL.passable is False


def test_tile_glyphs_are_single_characters():
    for tile in Tile:
        assert len(tile.glyph) == 1
