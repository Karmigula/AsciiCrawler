"""Assemble a drawable frame: what to draw, with no idea what draws it.

This is everything the desktop loop used to do between "the tick is done" and
"hand it to pygame" - the world window, the field of view, the fog shading,
the biome wash. It knows nothing about a screen, so the same frame feeds a
pygame surface and a browser canvas, and the two cannot drift into showing
different games.

The layering rule that made this cheap already held: `world/`, `agent/` and
`sim/` never imported pygame, and `render/` only ever read state it was
handed. All that was missing was a seam between deciding a frame and painting
it.
"""

from typing import Sequence

from agent.fov import compute_fov
from config import Config
from render.flourish import speckle_moss
from render.fog import fog_grid
from render.overlays import apply_overlay
from render.palette import background_grid, item_color, monster_color, terrain_color
from world.tiles import Tile

Position = tuple[int, int]
Color = tuple[int, int, int]


def terrain_palette(config: Config) -> dict[str, Color]:
    """Flat glyph colours, used only where no coordinate is available."""
    return {
        Tile.WALL.glyph: config.wall_color,
        Tile.FLOOR.glyph: config.floor_color,
        Tile.WATER.glyph: config.water_color,
        Tile.LAVA.glyph: config.lava_color,
    }


def thing_color(glyph: str, config: Config) -> Color:
    """Whatever is standing on a tile: monsters by threat, items by kind."""
    if glyph in config.monster_colors:
        return monster_color(glyph, config)
    return item_color(glyph, config)


def visible_from(world, agent, config: Config) -> set[Position]:
    """Visible set in global coordinates (window semantics match the tick)."""
    radius = agent.mind(config).fov_radius
    origin_x, origin_y = agent.x - radius, agent.y - radius
    window = [
        [world.tile_at(origin_x + lx, origin_y + ly) for lx in range(2 * radius + 1)]
        for ly in range(2 * radius + 1)
    ]
    return {
        (origin_x + lx, origin_y + ly)
        for lx, ly in compute_fov(window, (radius, radius), radius)
    }


def world_rows(world, origin: Position, cols: int, rows: int) -> list[str]:
    """The raw glyph window: what is actually there, before anyone believes it."""
    return [
        "".join(world.tile_at(origin[0] + x, origin[1] + y).glyph for x in range(cols))
        for y in range(rows)
    ]


def build_frame(
    world,
    agent,
    config: Config,
    origin: Position,
    cols: int,
    rows: int,
    overlay: str | None = None,
) -> tuple[list, list, Sequence[str]]:
    """Return (cells, backgrounds, rows_text) for a window at `origin`.

    `cells` is (glyph, colour) or None per tile, shaded by what the agent
    remembers and how long ago; `backgrounds` is the matching biome wash.
    Truth goes in, belief comes out - the window is built from `tile_at` and
    then dimmed through the same memory the brain plans on.
    """
    rows_text = world_rows(world, origin, cols, rows)
    visible = visible_from(world, agent, config)
    mind = agent.mind(config)
    cells = fog_grid(
        rows_text,
        terrain_palette(config),
        visible,
        agent.memory,
        config.remembered_brightness,
        origin=origin,
        tick=agent.tick_count,
        ttl=mind.memory_ttl,
        stale_factor=config.stale_brightness,
        stale_fraction=config.memory_stale_fraction,
        ghost_color=config.ghost_color,
        color_for=lambda glyph, coord: terrain_color(
            glyph, coord, config, world.biome_key_at(*coord)
        ),
        ghost_color_for=lambda glyph: thing_color(glyph, config),
        memory_tint=config.memory_tint_color,
        fresh_tint=config.fresh_tint,
        stale_tint=config.stale_tint,
    )
    cells = speckle_moss(cells, origin, Tile.FLOOR.glyph, config)
    if overlay is not None:
        cells = apply_overlay(cells, overlay, origin, agent, visible, mind)
    backgrounds = background_grid(
        rows_text,
        origin,
        visible,
        agent.memory,
        config,
        tick=agent.tick_count,
        ttl=mind.memory_ttl,
        biome_for=lambda coord: world.biome_key_at(*coord),
    )
    return cells, backgrounds, rows_text
