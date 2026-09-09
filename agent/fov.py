"""Recursive shadowcasting FOV: the only channel from world truth to agent belief.

Pure tile-coord computation — no pygame, no state, no entities (entities join
the visible set in a later phase). Walls block sight and are lit when they
block, which makes visibility symmetric: A sees B iff B sees A.
"""

from collections.abc import Sequence

from world.tiles import Tile

Position = tuple[int, int]

# (xx, xy, yx, yy) multipliers mapping the generic octant walk onto all 8 octants.
_OCTANTS: tuple[tuple[int, int, int, int], ...] = (
    (1, 0, 0, 1),
    (0, 1, 1, 0),
    (0, -1, 1, 0),
    (-1, 0, 0, 1),
    (-1, 0, 0, -1),
    (0, -1, -1, 0),
    (0, 1, -1, 0),
    (1, 0, 0, -1),
)


def compute_fov(
    tiles: Sequence[Sequence[Tile]],
    origin: Position,
    radius: int,
) -> set[Position]:
    """Return every tile visible from origin (origin included).

    Nothing at distance >= radius is visible (strict cutoff). Out-of-bounds
    tiles block sight and are never returned.
    """
    ox, oy = origin
    visible = {(ox, oy)}
    for xx, xy, yx, yy in _OCTANTS:
        _cast_light(tiles, ox, oy, radius, 1, 1.0, 0.0, xx, xy, yx, yy, visible)
    return visible


def _cast_light(
    tiles: Sequence[Sequence[Tile]],
    ox: int,
    oy: int,
    radius: int,
    row: int,
    start: float,
    end: float,
    xx: int,
    xy: int,
    yx: int,
    yy: int,
    visible: set[Position],
) -> None:
    """Cast one octant, recursing past blockers as their shadows narrow."""
    if start < end:
        return
    radius_squared = radius * radius
    width = len(tiles[0])
    height = len(tiles)
    new_start = 0.0
    for j in range(row, radius + 1):
        dx = -j - 1
        dy = -j
        blocked = False
        while dx <= 0:
            dx += 1
            x = ox + dx * xx + dy * xy
            y = oy + dx * yx + dy * yy
            l_slope = (dx - 0.5) / (dy + 0.5)
            r_slope = (dx + 0.5) / (dy - 0.5)
            if start < r_slope:
                continue
            if end > l_slope:
                break
            in_bounds = 0 <= x < width and 0 <= y < height
            if in_bounds and dx * dx + dy * dy < radius_squared:
                visible.add((x, y))
            opaque = not in_bounds or tiles[y][x] is Tile.WALL
            if blocked:
                if opaque:
                    new_start = r_slope
                    continue
                blocked = False
                start = new_start
            elif opaque and j < radius:
                blocked = True
                _cast_light(tiles, ox, oy, radius, j + 1, start, l_slope, xx, xy, yx, yy, visible)
                new_start = r_slope
        if blocked:
            break
