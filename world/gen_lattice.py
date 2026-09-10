"""The weave: a regular lattice with pieces missing.

Open floor cut by a grid of thin walls at a fixed period, and then a fraction
of those wall segments removed. What comes out is neither a maze nor a hall: a
regular structure with irregular gaps, the kind of shape that looks designed
without looking useful.

The most artificial terrain in the game, on purpose. Set against caves that
erode and stations that were built for a reason, the weave reads as something
whose reason is not available.
"""

import random

import numpy as np

from world.tiles import Tile


def generate(
    rng: random.Random,
    width: int,
    height: int,
    period: int,
    gap_chance: float,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: a lattice, imperfectly woven."""
    wall, floor = int(Tile.WALL), int(Tile.FLOOR)
    tiles = np.full((height, width), floor, dtype=np.int8)
    period = max(3, period)

    # Roll each strut once, up front. A strut is whole or missing along its
    # length; deciding per tile would make the lattice flicker rather than
    # break.
    struts: dict = {}
    for index in range(0, max(width, height) // period + 2):
        struts[("v", index)] = rng.random()
        struts[("h", index)] = rng.random()

    for y in range(height):
        for x in range(width):
            vertical = x % period == 0
            horizontal = y % period == 0
            if not (vertical or horizontal):
                continue
            key = ("v", x // period) if vertical else ("h", y // period)
            if struts[key] >= gap_chance:
                tiles[y, x] = wall

    tiles[0, :] = tiles[-1, :] = wall
    tiles[:, 0] = tiles[:, -1] = wall
    return tiles
