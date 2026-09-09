"""Tile enum: the vocabulary every world module speaks.

The set is exactly WALL, FLOOR, WATER, LAVA. WATER and LAVA are IMPASSABLE
to movement but do NOT block sight (only WALL is opaque — FOV treats every
non-WALL tile as transparent, a deliberate choice so pools read as open
space you cannot cross). Numeric codes suit numpy tile arrays.
"""

from enum import IntEnum


class Tile(IntEnum):
    WALL = 0
    FLOOR = 1
    WATER = 2
    LAVA = 3

    @property
    def glyph(self) -> str:
        return {Tile.WALL: "#", Tile.FLOOR: ".", Tile.WATER: "~", Tile.LAVA: "^"}[self]

    @property
    def passable(self) -> bool:
        return self is Tile.FLOOR
