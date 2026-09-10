"""Derelict station: orthogonal compartments joined by doorways.

Nothing here is eroded. The station was built, on a grid, by people who wanted
right angles - so the generator lays a fixed lattice of cells, hollows each one
into a compartment, and punches a doorway through the bulkhead between
neighbours. What makes it read as ruined is that not every door opens: some
bulkheads stay sealed, so the plan is regular but the route through it is not.

The contrast with `gen_ruins` is the point. Ruins are architecture decaying
into cave; a station is architecture that never decayed, just stopped.
"""

import random

import numpy as np

from world.tiles import Tile


def generate(
    rng: random.Random,
    width: int,
    height: int,
    cell: int,
    door_chance: float,
    sealed_chance: float,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: compartments and corridors."""
    wall, floor = int(Tile.WALL), int(Tile.FLOOR)
    tiles = np.full((height, width), wall, dtype=np.int8)
    cell = max(4, cell)

    cells_x = max(1, (width - 1) // cell)
    cells_y = max(1, (height - 1) // cell)

    # Hollow each compartment, leaving its bulkheads intact.
    for gy in range(cells_y):
        for gx in range(cells_x):
            if rng.random() < sealed_chance:
                continue  # a compartment that never opened
            left = gx * cell + 1
            top = gy * cell + 1
            right = min(width - 2, left + cell - 3)
            bottom = min(height - 2, top + cell - 3)
            if right <= left or bottom <= top:
                continue
            tiles[top : bottom + 1, left : right + 1] = floor

    # Punch doorways between neighbours. Not all of them: a station where every
    # door works is a grid, and a grid is not a place you can get lost in.
    for gy in range(cells_y):
        for gx in range(cells_x):
            left = gx * cell + 1
            top = gy * cell + 1
            if gx + 1 < cells_x and rng.random() < door_chance:
                x = min(width - 2, left + cell - 2)
                y = min(height - 2, top + (cell - 2) // 2)
                tiles[y, x] = floor
                tiles[y, min(width - 2, x + 1)] = floor
            if gy + 1 < cells_y and rng.random() < door_chance:
                x = min(width - 2, left + (cell - 2) // 2)
                y = min(height - 2, top + cell - 2)
                tiles[y, x] = floor
                tiles[min(height - 2, y + 1), x] = floor

    tiles[0, :] = tiles[-1, :] = wall
    tiles[:, 0] = tiles[:, -1] = wall
    return tiles
