"""Fog of war: brightness tiers over state handed in (never world truth).

Four tiers, and the top three are just brightness on the same glyph:

    visible   -> full colour
    fresh     -> remembered_factor (default 60%)
    stale     -> stale_factor (default 35%), once age passes stale_fraction
                 of the TTL
    expired   -> blank (None), same as never seen

The fourth tier is the point of the whole phase: knowledge older than the TTL
renders as unknown even before the pruner physically drops the record, so a
tile the agent has forgotten looks exactly like a tile it never saw. Passing
no `tick`/`ttl` keeps the old two-tier behaviour, which is what the callers
that do not model decay (and their tests) still want.

`known` is the agent's memory — render and brain share one belief store, and
this module never sees a world tile. When memory holds a snapshot of what
stood on a tile (a monster, an item), that glyph is drawn instead of the
terrain: at full strength while visible, dimmed by the tier factor once it is
only a memory. Remembered monsters and remembered loot take separate colours,
because they are different kinds of news and a watcher should be able to tell
them apart without reading the glyph.
"""

from collections.abc import Container, Mapping, Sequence

Color = tuple[int, int, int]
Position = tuple[int, int]
Cell = tuple[str, Color]

VISIBLE = "visible"
FRESH = "fresh"
STALE = "stale"
EXPIRED = "expired"
UNKNOWN = "unknown"


def shade(color: Color, factor: float) -> Color:
    """Scale each channel by factor (1.0 = unchanged, 0.6 = dimmed)."""
    r, g, b = color
    return round(r * factor), round(g * factor), round(b * factor)


def _toward(color: Color, target: Color, weight: float) -> Color:
    """Blend a colour toward another by weight (0 = unchanged)."""
    weight = max(0.0, min(1.0, weight))
    return (
        round(color[0] + (target[0] - color[0]) * weight),
        round(color[1] + (target[1] - color[1]) * weight),
        round(color[2] + (target[2] - color[2]) * weight),
    )


def tier_for(
    coord: Position,
    visible: Container[Position],
    known: Container[Position],
    *,
    tick: int | None = None,
    ttl: int | None = None,
    stale_fraction: float = 0.5,
    age_of=None,
) -> str:
    """Which of the five states a coordinate is in, for the caller's own use."""
    if coord in visible:
        return VISIBLE
    if coord not in known:
        return UNKNOWN
    if tick is None or ttl is None or age_of is None:
        return FRESH
    age = age_of(coord, tick)
    if age > ttl:
        return EXPIRED
    if age > ttl * stale_fraction:
        return STALE
    return FRESH


def fog_grid(
    rows: Sequence[str],
    palette: Mapping[str, Color],
    visible: set[Position],
    known: Container[Position],
    remembered_factor: float,
    *,
    origin: Position = (0, 0),
    tick: int | None = None,
    ttl: int | None = None,
    stale_factor: float | None = None,
    stale_fraction: float = 0.5,
    ghost_color: Color = (150, 150, 160),
    ghost_entity_color: Color | None = None,
    ghost_item_color: Color | None = None,
    color_for=None,
    ghost_color_for=None,
    memory_tint: Color | None = None,
    fresh_tint: float = 0.0,
    stale_tint: float = 0.0,
) -> list[list[Cell | None]]:
    """Build the drawable grid: (glyph, color) per tile, None for nothing known.

    `rows` is a window whose top-left cell sits at world coordinate `origin`;
    `visible` and `known` are world-coordinate sets, matched against the window
    through that offset (default (0, 0) keeps local-coordinate rows working).

    `color_for(glyph, coord)` overrides the flat palette when terrain colour
    depends on where the tile is - biome shading needs the coordinate, not just
    the glyph. `ghost_color_for(glyph)` does the same for whatever is standing
    on a tile. Both fall back to the palette and the flat ghost colours, which
    is what the callers that do not shade by position still want.
    """
    origin_x, origin_y = origin
    age_of = getattr(known, "age", None)
    snapshot_of = getattr(known, "snapshot", None)
    stale = remembered_factor if stale_factor is None else stale_factor
    grid: list[list[Cell | None]] = []
    for y, line in enumerate(rows):
        cells: list[Cell | None] = []
        for x, glyph in enumerate(line):
            coord = (x + origin_x, y + origin_y)
            tier = tier_for(
                coord,
                visible,
                known,
                tick=tick,
                ttl=ttl,
                stale_fraction=stale_fraction,
                age_of=age_of,
            )
            if tier in (UNKNOWN, EXPIRED):
                cells.append(None)
                continue
            factor = {VISIBLE: 1.0, FRESH: remembered_factor, STALE: stale}[tier]
            tint = {VISIBLE: 0.0, FRESH: fresh_tint, STALE: stale_tint}[tier]
            draw = glyph
            base = palette[glyph] if color_for is None else color_for(glyph, coord)
            if snapshot_of is not None:
                entity, item = snapshot_of(coord)
                if entity is not None:
                    # Remembered monsters and remembered loot are different
                    # kinds of news, and a watcher should be able to tell them
                    # apart at a glance without reading the glyph.
                    draw = entity
                    base = (
                        ghost_color_for(entity)
                        if ghost_color_for is not None
                        else (ghost_entity_color or ghost_color)
                    )
                elif item is not None:
                    draw = item
                    base = (
                        ghost_color_for(item)
                        if ghost_color_for is not None
                        else (ghost_item_color or ghost_color)
                    )
            if memory_tint is not None and tint > 0.0:
                base = _toward(base, memory_tint, tint)
            cells.append((draw, base if factor == 1.0 else shade(base, factor)))
        grid.append(cells)
    return grid
