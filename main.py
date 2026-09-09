"""Wiring, fixed-timestep game loop, and controls (ESC to quit).

The loop only orchestrates: ticks advance the agent through the infinite
chunk world, then rendering hands the screen a world-window of glyph rows
around the camera (built through `tile_at`), shades it through the same
memory the brain uses, and draws the agent on top. No decisions are made
here; the camera simply follows the agent across chunk borders.
"""

import random

import pygame

from agent.fov import compute_fov
from config import DEFAULT_CONFIG, Config
from render.fog import fog_grid
from render.screen import Screen
from sim.tick import AgentState, tick
from world.chunks import ChunkStore
from world.tiles import Tile


def main(config: Config = DEFAULT_CONFIG) -> None:
    world = ChunkStore(config, world_seed=config.world_seed)
    spawn = world.spawn
    rng = random.Random(config.tick_seed)
    agent = AgentState(x=spawn[0], y=spawn[1])
    palette = {
        Tile.WALL.glyph: config.wall_color,
        Tile.FLOOR.glyph: config.floor_color,
        Tile.WATER.glyph: config.water_color,
        Tile.LAVA.glyph: config.lava_color,
    }
    screen = Screen(config)
    clock = pygame.time.Clock()
    tick_duration = 1.0 / config.tps
    accumulator = 0.0
    running = True
    while running:
        dt = clock.tick(config.max_fps) / 1000.0
        accumulator = min(accumulator + dt, config.max_frame_seconds)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
        while accumulator >= tick_duration:
            tick(agent, world, rng, config)
            accumulator -= tick_duration
        camera = (agent.x, agent.y)
        origin = screen.camera_origin(camera)
        cols, rows = screen.view_dims
        rows_text = [
            "".join(
                world.tile_at(origin[0] + x, origin[1] + y).glyph
                for x in range(cols)
            )
            for y in range(rows)
        ]
        visible = _fov_global(world, agent, config)
        cells = fog_grid(
            rows_text,
            palette,
            visible,
            agent.memory,
            config.remembered_brightness,
            origin=origin,
            tick=agent.tick_count,
            ttl=config.memory_ttl,
            stale_factor=config.stale_brightness,
            stale_fraction=config.memory_stale_fraction,
            ghost_color=config.ghost_color,
        )
        screen.draw_cells(cells)
        screen.draw_glyph(config.agent_glyph, agent.x, agent.y, camera, config.agent_color)
        screen.present()
    screen.close()


def _fov_global(world: ChunkStore, agent: AgentState, config: Config) -> set[tuple[int, int]]:
    """Visible set in global coordinates (window semantics match the tick)."""
    radius = config.fov_radius
    origin_x, origin_y = agent.x - radius, agent.y - radius
    window = [
        [world.tile_at(origin_x + lx, origin_y + ly) for lx in range(2 * radius + 1)]
        for ly in range(2 * radius + 1)
    ]
    return {
        (origin_x + lx, origin_y + ly)
        for lx, ly in compute_fov(window, (radius, radius), radius)
    }


if __name__ == "__main__":
    main()
