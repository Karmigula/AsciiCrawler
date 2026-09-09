import random

from agent.fov import compute_fov
from config import DEFAULT_CONFIG
from world.gen_bsp import generate
from world.tiles import Tile


def _open_field(width: int = 41, height: int = 41) -> list[list[Tile]]:
    """A FLOOR interior enclosed by a WALL border."""
    return [
        [
            Tile.WALL if x in (0, width - 1) or y in (0, height - 1) else Tile.FLOOR
            for x in range(width)
        ]
        for y in range(height)
    ]


def test_fov_origin_is_always_visible():
    assert (20, 20) in compute_fov(_open_field(), (20, 20), 8)


def test_fov_open_area_is_exact_radius_disc():
    visible = compute_fov(_open_field(), (20, 20), 8)
    expected = {
        (20 + dx, 20 + dy)
        for dx in range(-8, 9)
        for dy in range(-8, 9)
        if dx * dx + dy * dy < 64
    }
    assert visible == expected


def test_fov_nothing_beyond_radius():
    visible = compute_fov(_open_field(), (20, 20), 5)
    for x, y in visible:
        assert (x - 20) ** 2 + (y - 20) ** 2 < 25
    assert (25, 20) not in visible  # exactly at radius -> cut off
    assert (24, 20) in visible


def test_fov_symmetric_for_all_open_area_pairs():
    tiles = _open_field()
    for dx in range(-7, 8):
        for dy in range(-7, 8):
            if dx * dx + dy * dy >= 49 or (dx, dy) == (0, 0):
                continue
            a, b = (20, 20), (20 + dx, 20 + dy)
            a_sees_b = b in compute_fov(tiles, a, 8)
            b_sees_a = a in compute_fov(tiles, b, 8)
            assert a_sees_b == b_sees_a, (a, b)


def test_fov_wall_blocks_and_is_lit_itself():
    tiles = _open_field()
    for y in range(6, 35):
        tiles[y][20] = Tile.WALL
    visible = compute_fov(tiles, (16, 20), 8)
    assert (20, 20) in visible  # the wall face along the sightline
    assert (21, 20) not in visible  # directly behind the wall run
    assert (24, 20) not in visible


def test_fov_sealed_room_leaks_nothing():
    tiles = [[Tile.WALL] * 21 for _ in range(21)]
    for y in range(6, 15):
        for x in range(6, 15):
            tiles[y][x] = Tile.FLOOR
    visible = compute_fov(tiles, (10, 10), 9)
    assert all(5 <= x <= 15 and 5 <= y <= 15 for x, y in visible)
    assert (5, 10) in visible  # room walls are lit
    assert (4, 10) not in visible
    assert (10, 4) not in visible


def test_fov_symmetric_inside_a_generated_room():
    cfg = DEFAULT_CONFIG
    tiles = generate(
        random.Random(cfg.map_seed), cfg.map_width, cfg.map_height,
        cfg.bsp_min_partition, cfg.bsp_min_room,
    )
    open_cells = [
        (x, y)
        for y in range(3, cfg.map_height - 3)
        for x in range(3, cfg.map_width - 3)
        if all(tiles[yy][xx] is Tile.FLOOR for yy in range(y - 3, y + 4) for xx in range(x - 3, x + 4))
    ]
    assert open_cells, "expected at least one 7x7 open area in the generated map"
    center = open_cells[0]
    checked = 0
    for other in open_cells[1:]:
        if max(abs(center[0] - other[0]), abs(center[1] - other[1])) > 3:
            continue
        x0, x1 = sorted((center[0], other[0]))
        y0, y1 = sorted((center[1], other[1]))
        if all(tiles[y][x] is Tile.FLOOR for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)):
            assert (other in compute_fov(tiles, center, 8)) == (
                center in compute_fov(tiles, other, 8)
            ), (center, other)
            checked += 1
    assert checked, "expected at least one clear nearby pair in a room"
