"""Overgrown ruins: rooms and corridors that the rock has been taking back.

Built by laying out a BSP floorplan and then running a few cellular-automata
steps over it. The automaton rounds corners, breaks walls where they were thin,
and closes off the odd doorway, so what is left reads as architecture that has
lost an argument with time - straight enough to have been built, ragged enough
to be ruined.

The room floors are protected from being filled back in, so the plan survives
as the bones of the place even where the walls have gone.
"""

import random

import numpy as np

from world import gen_bsp
from world.gen_cave import ca_step
from world.tiles import Tile


def generate(
    rng: random.Random,
    width: int,
    height: int,
    min_partition: int,
    min_room: int,
    fill_prob: float,
    smooth_steps: int,
    wall_threshold: int,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: a floorplan gone to seed."""
    grid = gen_bsp.generate(rng, width, height, min_partition, min_room)
    tiles = np.array([[int(tile) for tile in row] for row in grid], dtype=np.int8)
    floor, wall = int(Tile.FLOOR), int(Tile.WALL)

    # Where the plan put floor, remember it: erosion may take the walls, but
    # the rooms themselves stay legible.
    protected = tiles == floor

    # Sprinkle rubble through the open space, then let the automaton settle it.
    walls = tiles == wall
    for y in range(height):
        for x in range(width):
            if not walls[y, x] and rng.random() < fill_prob * 0.35:
                walls[y, x] = True

    for _ in range(max(0, smooth_steps)):
        walls = ca_step(walls, wall_threshold)

    grown = np.where(walls, wall, floor).astype(np.int8)
    # Half the protected floor comes back: enough for the plan to show through,
    # ragged enough that it does not look freshly swept.
    # Seeded from the chunk's own rng, never numpy's global state: two chunks
    # generated in a different order must still come out identical.
    rolls = np.fromiter(
        (rng.random() for _ in range(width * height)), dtype=float, count=width * height
    ).reshape(height, width)
    grown[protected & (rolls < 0.55)] = floor
    grown[0, :] = wall
    grown[-1, :] = wall
    grown[:, 0] = wall
    grown[:, -1] = wall
    return grown
