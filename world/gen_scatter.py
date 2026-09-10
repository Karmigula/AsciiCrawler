"""Scattering a tile across finished terrain in patches rather than confetti.

Frozen drifts and drifting spores are not features of a floorplan, they are
something that settled on one afterwards. So they are a post-pass: build the
cave, then decide which parts of its floor are ice, or fog, or whatever comes
next.

Clumped by the same cellular automaton the caves use, because scattered
per-tile noise reads as static and a drift reads as a place.
"""

import random

import numpy as np

from world.gen_cave import ca_step
from world.tiles import Tile


def scatter(
    tiles: np.ndarray,
    rng: random.Random,
    tile: int,
    chance: float,
    smooth_steps: int = 3,
    wall_threshold: int = 5,
) -> None:
    """In place: turn clumps of FLOOR into `tile`.

    Only FLOOR is eligible - walls stay walls and liquids stay liquid, so a
    drift never seals a pool or eats the structure it settled on.
    """
    if chance <= 0.0:
        return
    height, width = tiles.shape
    rolls = np.fromiter(
        (rng.random() for _ in range(width * height)), dtype=float, count=width * height
    ).reshape(height, width)
    patch = rolls < chance
    for _ in range(max(0, smooth_steps)):
        patch = ca_step(patch, wall_threshold)
    tiles[(tiles == int(Tile.FLOOR)) & patch] = tile
