"""Seeded BSP dungeon generator: rooms in leaf partitions, corridors between.

Classic Rogue look: binary space partition into rectangles, one room per leaf,
siblings joined by an L-shaped corridor with a random dogleg. Pure function of
(rng, bounds, params) with no globals, so Phase 3 can call it per-chunk.
"""

import random

from world.tiles import Tile

Rect = tuple[int, int, int, int]  # x, y, width, height
Point = tuple[int, int]


def generate(
    rng: random.Random,
    width: int,
    height: int,
    min_partition: int,
    min_room: int,
) -> list[list[Tile]]:
    """Return a width x height grid; WALL except rooms, corridors, never border.

    Deterministic for a fixed seed. Degenerate sizes yield an all-WALL grid.
    """
    grid = [[Tile.WALL] * width for _ in range(height)]
    if width < 3 or height < 3:
        return grid
    _grow(rng, grid, 1, 1, width - 2, height - 2, min_partition, min_room)
    return grid


def _grow(
    rng: random.Random,
    grid: list[list[Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    min_partition: int,
    min_room: int,
) -> Point | None:
    """Partition (x, y, w, h) recursively; carve rooms, join siblings.

    Returns a room center of this subtree so the parent can connect to it, or
    None when the region is too small to hold a room.
    """
    split = _pick_split(rng, x, y, w, h, min_partition)
    if split is None:
        return _carve_room(rng, grid, x, y, w, h, min_room)
    (ax, ay, aw, ah), (bx, by, bw, bh) = split
    center_a = _grow(rng, grid, ax, ay, aw, ah, min_partition, min_room)
    center_b = _grow(rng, grid, bx, by, bw, bh, min_partition, min_room)
    if center_a is None or center_b is None:
        return center_a if center_a is not None else center_b
    _carve_corridor(rng, grid, center_a, center_b)
    return rng.choice((center_a, center_b))


def _pick_split(
    rng: random.Random,
    x: int,
    y: int,
    w: int,
    h: int,
    min_partition: int,
) -> tuple[Rect, Rect] | None:
    """Split the rect on a random axis, or None when both halves would be too small."""
    can_vertical = w >= 2 * min_partition
    can_horizontal = h >= 2 * min_partition
    if not can_vertical and not can_horizontal:
        return None
    vertical = rng.random() < 0.5 if can_vertical and can_horizontal else can_vertical
    if vertical:
        left = rng.randint(min_partition, w - min_partition)
        return (x, y, left, h), (x + left, y, w - left, h)
    top = rng.randint(min_partition, h - min_partition)
    return (x, y, w, top), (x, y + top, w, h - top)


def _carve_room(
    rng: random.Random,
    grid: list[list[Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    min_room: int,
) -> Point | None:
    """Carve a random room inside the leaf with a 1-tile wall margin; return its center."""
    room_w = min(rng.randint(min_room, max(min_room, w - 2)), w - 2)
    room_h = min(rng.randint(min_room, max(min_room, h - 2)), h - 2)
    if room_w <= 0 or room_h <= 0:
        return None
    rx = rng.randint(x + 1, x + w - room_w - 1)
    ry = rng.randint(y + 1, y + h - room_h - 1)
    for yy in range(ry, ry + room_h):
        for xx in range(rx, rx + room_w):
            grid[yy][xx] = Tile.FLOOR
    return rx + room_w // 2, ry + room_h // 2


def _carve_corridor(rng: random.Random, grid: list[list[Tile]], a: Point, b: Point) -> None:
    """Carve an L corridor with a random dogleg column between two room centers."""
    ax, ay = a
    bx, by = b
    if rng.random() < 0.5:
        ax, ay, bx, by = bx, by, ax, ay
    turn = rng.randint(min(ax, bx), max(ax, bx))
    _carve_h(grid, ax, turn, ay)
    _carve_v(grid, ay, by, turn)
    _carve_h(grid, turn, bx, by)


def _carve_h(grid: list[list[Tile]], x1: int, x2: int, y: int) -> None:
    for x in range(min(x1, x2), max(x1, x2) + 1):
        grid[y][x] = Tile.FLOOR


def _carve_v(grid: list[list[Tile]], y1: int, y2: int, x: int) -> None:
    for y in range(min(y1, y2), max(y1, y2) + 1):
        grid[y][x] = Tile.FLOOR
