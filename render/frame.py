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

SHRINE_GLYPH = "&"
SHOP_GLYPH = "%"

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
    if glyph == SHRINE_GLYPH:
        return config.shrine_color
    if glyph == SHOP_GLYPH:
        return config.shop_color
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


def paint_bolts(cells, origin: Position, agent):
    """Draw whatever was thrown recently on top of the world.

    Over everything, including the fog: a bolt is happening now and in the
    light of its own making. Anything off the window is skipped rather than
    clamped, so a fight at the edge does not smear down the side of it.
    """
    flashes = getattr(agent, "flashes", None)
    if not flashes:
        return cells
    height = len(cells)
    width = len(cells[0]) if height else 0
    for (x, y), glyph, colour, _left in flashes:
        column, row = x - origin[0], y - origin[1]
        if 0 <= row < height and 0 <= column < width:
            cells[row][column] = (glyph, colour)
    return cells


def boss_in_view(world, agent, config: Config):
    """The named thing the agent can see, as (name, hp, full), or None.

    Only what is actually visible: a bar for something behind a wall would be
    telling the watcher what the creature does not know, and this whole game
    is built on not doing that.
    """
    from sim.bosses import GLYPHS

    entity_at = getattr(world, "entity_at", None)
    if entity_at is None:
        return None
    for coord in visible_from(world, agent, config):
        monster = entity_at(*coord)
        if monster is None or monster.kind.glyph not in GLYPHS:
            continue
        return (monster.name or monster.kind.key, max(0, monster.hp), monster.kind.hp)
    return None


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
    shades_out: list | None = None,
    biomes_out: list | None = None,
) -> tuple[list, list, Sequence[str]]:
    """Return (cells, backgrounds, rows_text) for a window at `origin`.

    `cells` is (glyph, colour) or None per tile, shaded by what the agent
    remembers and how long ago; `backgrounds` is the matching biome wash.
    `shades_out`, if given, is filled with the brightness behind each of those
    colours, and `biomes_out` with the biome each cell stands in - only a
    texture pack needs either, and only the window has them. Which biome a
    wall belongs to is a fact about the world, not about belief: the creature
    is looking at rock it can see, and rock in the frozen deep looks like ice
    whether or not it has been there before.
    Truth goes in, belief comes out - the window is built from `tile_at` and
    then dimmed through the same memory the brain plans on.
    """
    rows_text = world_rows(world, origin, cols, rows)
    # One lookup per tile, shared by the glyph colour, the background wash and
    # the pack's per-biome art, all three of which want the same answer.
    known_biomes: dict = {}

    def biome_key(coord):
        found = known_biomes.get(coord)
        if found is None:
            found = known_biomes[coord] = world.biome_key_at(*coord)
        return found

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
            glyph, coord, config, biome_key(coord)
        ),
        ghost_color_for=lambda glyph: thing_color(glyph, config),
        memory_tint=config.memory_tint_color,
        fresh_tint=config.fresh_tint,
        stale_tint=config.stale_tint,
        shades_out=shades_out,
    )
    cells = speckle_moss(cells, origin, Tile.FLOOR.glyph, config)
    cells = paint_bolts(cells, origin, agent)
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
        biome_for=biome_key,
    )
    if biomes_out is not None:
        biomes_out[:] = [
            [biome_key((origin[0] + x, origin[1] + y)) for x in range(cols)]
            for y in range(rows)
        ]
    return cells, backgrounds, rows_text
