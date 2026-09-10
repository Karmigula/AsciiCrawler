"""Machine halls: a dense maze on a fixed grid.

A recursive-backtracker maze carved on odd coordinates, so corridors are one
tile wide and walls are one tile thick. The result is the most claustrophobic
terrain in the game and the hardest to navigate - which is the point: it is the
inside of a machine, laid out for cable runs rather than for walking.

Braided a little at the end: a fraction of dead ends get a second opening. A
perfect maze has exactly one route between any two points, and an agent that
plans on remembered ground finds that miserable rather than interesting.
"""

import random

import numpy as np

from world.tiles import Tile


def generate(
    rng: random.Random, width: int, height: int, braid: float = 0.25
) -> np.ndarray:
    """Return a (height, width) int8 tile array: one-tile corridors on a grid."""
    wall, floor = int(Tile.WALL), int(Tile.FLOOR)
    tiles = np.full((height, width), wall, dtype=np.int8)

    # Cells live on odd coordinates; the wall between two cells is the even
    # coordinate they share.
    cells_x = max(1, (width - 1) // 2)
    cells_y = max(1, (height - 1) // 2)

    def cell_to_tile(cx: int, cy: int) -> tuple[int, int]:
        return cx * 2 + 1, cy * 2 + 1

    start = (rng.randrange(cells_x), rng.randrange(cells_y))
    seen = {start}
    stack = [start]
    tiles[cell_to_tile(*start)[1], cell_to_tile(*start)[0]] = floor

    while stack:
        cx, cy = stack[-1]
        options = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < cells_x and 0 <= ny < cells_y and (nx, ny) not in seen:
                options.append((nx, ny, dx, dy))
        if not options:
            stack.pop()
            continue
        nx, ny, dx, dy = options[rng.randrange(len(options))]
        x, y = cell_to_tile(cx, cy)
        tiles[y + dy, x + dx] = floor  # the wall between them
        tiles[cell_to_tile(nx, ny)[1], cell_to_tile(nx, ny)[0]] = floor
        seen.add((nx, ny))
        stack.append((nx, ny))

    if braid > 0:
        _braid(tiles, rng, cells_x, cells_y, braid, floor)

    tiles[0, :] = tiles[-1, :] = wall
    tiles[:, 0] = tiles[:, -1] = wall
    return tiles


def _braid(tiles, rng, cells_x, cells_y, braid, floor) -> None:
    """Open a second way out of some dead ends, so routes are not unique."""
    height, width = tiles.shape
    for cy in range(cells_y):
        for cx in range(cells_x):
            x, y = cx * 2 + 1, cy * 2 + 1
            if tiles[y, x] != floor:
                continue
            exits = [
                (dx, dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= x + dx < width and 0 <= y + dy < height
                and tiles[y + dy, x + dx] == floor
            ]
            if len(exits) > 1 or rng.random() >= braid:
                continue
            blocked = [
                (dx, dy)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 < x + dx < width - 1 and 0 < y + dy < height - 1
                and tiles[y + dy, x + dx] != floor
            ]
            if blocked:
                dx, dy = blocked[rng.randrange(len(blocked))]
                tiles[y + dy, x + dx] = floor
