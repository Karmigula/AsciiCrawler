"""Wiring, fixed-timestep game loop, and controls (ESC to quit)."""

import random

import pygame

from config import DEFAULT_CONFIG, Config
from render.screen import Screen
from sim.tick import AgentState, tick
from world.hardcoded import Tile, build_map


def main(config: Config = DEFAULT_CONFIG) -> None:
    tiles = build_map(config.map_width, config.map_height)
    rows = ["".join(tile.glyph for tile in row) for row in tiles]
    palette = {Tile.WALL.glyph: config.wall_color, Tile.FLOOR.glyph: config.floor_color}
    rng = random.Random(config.tick_seed)
    agent = AgentState(x=config.map_width // 2, y=config.map_height // 2)
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
            tick(agent, tiles, rng)
            accumulator -= tick_duration
        camera = (agent.x, agent.y)
        screen.draw_map(rows, camera, palette)
        screen.draw_glyph(config.agent_glyph, agent.x, agent.y, camera, config.agent_color)
        screen.present()
    screen.close()


if __name__ == "__main__":
    main()
