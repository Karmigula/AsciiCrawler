"""Cellular-automata cave generator: blobby caverns for the mid biome band.

Random fill (seeded python RNG, raster order), then `smooth_steps` passes of
the classic majority rule — a cell is WALL when at least `wall_threshold` of
its 3x3 neighbourhood (including itself) is wall. Smoothing is numpy-
vectorised but draws no randomness, so the result is a pure function of the
rng state handed in. The outer border is forced WALL so chunk seams stay
solid until the seam corridors punch through them.
"""

import random

import numpy as np

from world.tiles import Tile


def generate(
    rng: random.Random,
    width: int,
    height: int,
    fill_prob: float,
    smooth_steps: int,
    wall_threshold: int,
) -> np.ndarray:
    """Return a (height, width) int8 tile array: CA cave, WALL border."""
    walls = ca_walls(rng, width, height, fill_prob, smooth_steps, wall_threshold)
    return np.where(walls, int(Tile.WALL), int(Tile.FLOOR)).astype(np.int8)


def ca_walls(
    rng: random.Random,
    width: int,
    height: int,
    fill_prob: float,
    smooth_steps: int,
    wall_threshold: int,
) -> np.ndarray:
    """The boolean wall grid behind `generate` — shared with gen_cavern."""
    walls = _fill(rng, width, height, fill_prob)
    for _ in range(smooth_steps):
        walls = _smooth(walls, wall_threshold)
    return walls


def _fill(rng: random.Random, width: int, height: int, fill_prob: float) -> np.ndarray:
    """Random walls at fill_prob (raster draw order), solid border."""
    rolls = np.fromiter(
        (rng.random() for _ in range(width * height)),
        dtype=float,
        count=width * height,
    ).reshape(height, width)
    walls = rolls < fill_prob
    walls[0, :] = walls[-1, :] = True
    walls[:, 0] = walls[:, -1] = True
    return walls


def _smooth(walls: np.ndarray, wall_threshold: int) -> np.ndarray:
    """One majority-rule pass; out-of-grid neighbours count as wall."""
    height, width = walls.shape
    padded = np.pad(walls.astype(np.int16), 1, constant_values=1)
    count = np.zeros((height, width), dtype=np.int16)
    for dy in range(3):
        for dx in range(3):
            count += padded[dy : dy + height, dx : dx + width]
    out = count >= wall_threshold
    out[0, :] = out[-1, :] = True
    out[:, 0] = out[:, -1] = True
    return out
