"""Sealed chambers, and what is waiting in them.

A secret room is carved after the rest of the chunk is finished and after the
pass that guarantees everything is reachable - deliberately, because the whole
point is that it is not. No corridor runs to it, no seam touches it, and the
agent can walk past the wall for an hour without knowing.

What it holds is decided when the door opens rather than when the chunk is
made, the same rule the bosses follow: a hoard rolled at worldgen is either a
windfall the creature cannot use yet or junk by the time it arrives.

Nothing here reaches for the agent. It carves rock and says what sort of room
it made; the tick decides when somebody notices.
"""

import random

import numpy as np

from world.tiles import Tile

# What sorts of room there are, and how often each turns up. A trap is the
# rarest because finding one should feel like bad luck rather than a tax on
# curiosity.
KINDS: tuple[tuple[str, float], ...] = (
    ("hoard", 0.34),
    ("well", 0.26),
    ("gate", 0.24),
    ("trap", 0.16),
)

LABELS = {
    "hoard": "a hoard",
    "well": "a still pool",
    "gate": "a humming arch",
    "trap": "a baited room",
}


def pick_kind(rng: random.Random) -> str:
    """Roll one sort of room."""
    point = rng.random() * sum(weight for _, weight in KINDS)
    for key, weight in KINDS:
        point -= weight
        if point < 0:
            return key
    return KINDS[-1][0]


ROOM = 3  # the chamber is this many tiles across


def carve(tiles: np.ndarray, rng: random.Random, size: int) -> tuple | None:
    """Hollow a sealed chamber out of solid rock; return its centre, or None.

    Only ever cut into rock that is already rock on every side of the room,
    so a secret room never opens onto anything by accident and never eats a
    corridor somebody needs. If there is nowhere in this chunk with that much
    stone to spare, there is no secret room in this chunk.
    """
    height, width = tiles.shape
    room = ROOM
    margin = room // 2 + 2
    for _ in range(40):
        cx = rng.randrange(margin, width - margin)
        cy = rng.randrange(margin, height - margin)
        half = room // 2 + 1
        block = tiles[cy - half : cy + half + 1, cx - half : cx + half + 1]
        if block.size == 0 or not np.all(block == int(Tile.WALL)):
            continue  # not enough rock: carving here would open onto a hall
        low = room // 2
        tiles[cy - low : cy + low + 1, cx - low : cx + low + 1] = int(Tile.FLOOR)
        return cx, cy
    return None


def open_door(tiles: np.ndarray, centre: tuple, size: int) -> bool:
    """Break through the wall, joining the chamber to whatever is outside.

    Walks outward from the room in each direction until it meets open floor,
    then clears the rock between. The first direction that reaches anything
    wins, so the door appears on the side the corridor is actually on.

    The walk starts outside the chamber, which is not a detail: starting one
    tile from the centre meant starting on the room's own floor, so it found
    open ground immediately, cleared nothing, and cheerfully reported that it
    had opened a door. The room stayed sealed forever and nothing said so.
    """
    height, width = tiles.shape
    cx, cy = centre
    edge = ROOM // 2 + 1
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        path = []
        x, y = cx + dx * edge, cy + dy * edge
        while 0 < x < width - 1 and 0 < y < height - 1:
            if tiles[y, x] == int(Tile.WALL):
                path.append((x, y))
                x, y = x + dx, y + dy
                continue
            # Open ground at last: clear the rock we walked through.
            for px, py in path:
                tiles[py, px] = int(Tile.FLOOR)
            return True
        if len(path) > max(width, height):
            break
    return False
