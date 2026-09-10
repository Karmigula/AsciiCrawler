"""Sunken cathedral: flooded floor with causeways above the waterline.

Mostly water. What is walkable is a handful of long straight causeways -
the tops of walls, or what is left of a colonnade - crossing the flood, with
platforms where they meet. Water is impassable, so the causeways *are* the
map: a place where the route is obvious and the detours do not exist.

Deliberately the opposite problem from the maze. There, everything is
walkable and nothing is direct; here, almost nothing is walkable and what
remains runs straight.
"""

import random

import numpy as np

from world.tiles import Tile


def generate(
    rng: random.Random,
    width: int,
    height: int,
    causeways: int,
    platform_chance: float,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: causeways over deep water."""
    wall, floor, water = int(Tile.WALL), int(Tile.FLOOR), int(Tile.WATER)
    tiles = np.full((height, width), water, dtype=np.int8)

    lanes_x = sorted(rng.sample(range(4, width - 4), max(1, causeways)))
    lanes_y = sorted(rng.sample(range(4, height - 4), max(1, causeways)))

    for x in lanes_x:
        tiles[1 : height - 1, x] = floor
    for y in lanes_y:
        tiles[y, 1 : width - 1] = floor

    # Platforms where causeways cross: somewhere to stand, and something for
    # the eye to rest on in a field of water.
    for x in lanes_x:
        for y in lanes_y:
            if rng.random() >= platform_chance:
                continue
            radius = rng.randint(1, 3)
            top, bottom = max(1, y - radius), min(height - 2, y + radius)
            left, right = max(1, x - radius), min(width - 2, x + radius)
            tiles[top : bottom + 1, left : right + 1] = floor

    tiles[0, :] = tiles[-1, :] = wall
    tiles[:, 0] = tiles[:, -1] = wall
    return tiles
