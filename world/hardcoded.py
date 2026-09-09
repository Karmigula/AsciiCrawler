"""Hardcoded placeholder map, replaced by the BSP generator in Phase 1."""

from enum import IntEnum


class Tile(IntEnum):
    WALL = 0
    FLOOR = 1

    @property
    def glyph(self) -> str:
        return "#" if self is Tile.WALL else "."

    @property
    def passable(self) -> bool:
        return self is Tile.FLOOR


def build_map(width: int, height: int) -> list[list[Tile]]:
    """Return a width x height grid of FLOOR enclosed by a WALL border."""
    return [
        [
            Tile.WALL if x in (0, width - 1) or y in (0, height - 1) else Tile.FLOOR
            for x in range(width)
        ]
        for y in range(height)
    ]
