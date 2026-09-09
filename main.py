"""Wiring, fixed-timestep game loop, and controls (ESC to quit).

The loop only orchestrates: ticks advance agent + memory, then rendering
recomputes FOV for the frame and shades it through the same memory the
brain uses. No decisions are made here.
"""

import random

import pygame

from agent.fov import compute_fov
from config import DEFAULT_CONFIG, Config
from render.fog import fog_grid
from render.screen import Screen
from sim.harness import spawn_position
from sim.tick import AgentState, tick
from world.gen_bsp import generate
from world.tiles import Tile


def main(config: Config = DEFAULT_CONFIG) -> None:
    tiles = generate(
        random.Random(config.map_seed),
        config.map_width,
        config.map_height,
        config.bsp_min_partition,
        config.bsp_min_room,
    )
    rows = ["".join(tile.glyph for tile in row) for row in tiles]
    palette = {Tile.WALL.glyph: config.wall_color, Tile.FLOOR.glyph: config.floor_color}
    rng = random.Random(config.tick_seed)
    spawn_x, spawn_y = spawn_position(tiles, config.map_width // 2, config.map_height // 2)
    agent = AgentState(x=spawn_x, y=spawn_y)
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
            tick(agent, tiles, rng, config)
            accumulator -= tick_duration
        fov = compute_fov(tiles, (agent.x, agent.y), config.fov_radius)
        cells = fog_grid(rows, palette, fov, agent.memory, config.remembered_brightness)
        camera = (agent.x, agent.y)
        screen.draw_cells(cells, camera)
        screen.draw_glyph(config.agent_glyph, agent.x, agent.y, camera, config.agent_color)
        screen.present()
    screen.close()


if __name__ == "__main__":
    main()
