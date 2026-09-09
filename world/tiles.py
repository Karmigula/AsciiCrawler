"""Tile enum: the vocabulary every world module speaks."""

from enum import IntEnum


class Tile(IntEnum):
    """Numeric codes suit numpy arrays later; WATER/LAVA arrive in Phase 3."""

    WALL = 0
    FLOOR = 1

    @property
    def glyph(self) -> str:
        return "#" if self is Tile.WALL else "."

    @property
    def passable(self) -> bool:
        return self is Tile.FLOOR
