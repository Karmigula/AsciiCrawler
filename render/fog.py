"""Fog of war: brightness tiers over state handed in (never world truth).

visible -> full color; remembered (in memory, not currently visible) -> a
scaled-down variant; never seen -> blank (None). `known` is the agent's
memory (anything supporting `in`), so render and brain share one belief
store. Visible tiles are observed into memory by the tick that precedes
rendering, so the visible tier is always also remembered. Phase 3 will use
last-seen ticks for decay.
"""

from collections.abc import Container, Mapping, Sequence

Color = tuple[int, int, int]
Position = tuple[int, int]
Cell = tuple[str, Color]


def shade(color: Color, factor: float) -> Color:
    """Scale each channel by factor (1.0 = unchanged, 0.6 = dimmed)."""
    r, g, b = color
    return round(r * factor), round(g * factor), round(b * factor)


def fog_grid(
    rows: Sequence[str],
    palette: Mapping[str, Color],
    visible: set[Position],
    known: Container[Position],
    remembered_factor: float,
) -> list[list[Cell | None]]:
    """Build the drawable grid: (glyph, color) per tile, None for never-seen."""
    grid: list[list[Cell | None]] = []
    for y, line in enumerate(rows):
        cells: list[Cell | None] = []
        for x, glyph in enumerate(line):
            base = palette[glyph]
            if (x, y) in visible:
                cells.append((glyph, base))
            elif (x, y) in known:
                cells.append((glyph, shade(base, remembered_factor)))
            else:
                cells.append(None)
        grid.append(cells)
    return grid
