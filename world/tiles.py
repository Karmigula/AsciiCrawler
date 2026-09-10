"""Tile enum: the vocabulary every world module speaks.

WALL, FLOOR, WATER, LAVA, ICE, HAZE. Only WALL blocks sight - FOV treats every
other tile as transparent, a deliberate choice so pools and drifts read as open
ground you cannot always cross.

Passability is a property of the tile, and the two newest ones are passable but
not free: ICE is walked on and slid across, HAZE is walked through and hurts.
Anything reading `passable` gets the movement rule right by default; the cost
of crossing is applied by the tick, which is the only place that knows what is
doing the crossing.

Numeric codes suit numpy tile arrays, and they are append-only: a saved world
is a grid of these numbers, so reordering them would rewrite history.
"""

from enum import IntEnum


class Tile(IntEnum):
    WALL = 0
    FLOOR = 1
    WATER = 2
    LAVA = 3
    ICE = 4
    HAZE = 5

    @property
    def glyph(self) -> str:
        return {
            Tile.WALL: "#",
            Tile.FLOOR: ".",
            Tile.WATER: "~",
            Tile.LAVA: "^",
            Tile.ICE: "_",
            Tile.HAZE: "*",
        }[self]

    @property
    def passable(self) -> bool:
        """Whether a creature can enter this tile at all."""
        return self in (Tile.FLOOR, Tile.ICE, Tile.HAZE)

    @property
    def slippery(self) -> bool:
        """Entering this tile carries you one more step the same way."""
        return self is Tile.ICE

    @property
    def harmful(self) -> bool:
        """Standing in this tile costs hit points every tick."""
        return self is Tile.HAZE
