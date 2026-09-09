"""Wiring, fixed-timestep game loop, and controls (ESC to quit)."""

import random
from collections.abc import Sequence

import pygame

from agent.fov import compute_fov
from config import DEFAULT_CONFIG, Config
from render.fog import fog_grid
from render.screen import Screen
from sim.tick import AgentState, tick
from world.gen_bsp import generate
from world.tiles import Tile


def _spawn(tiles: Sequence[Sequence[Tile]], center_x: int, center_y: int) -> tuple[int, int]:
    """Deterministic spawn: the FLOOR cell nearest the map center."""
    floors = (
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile is Tile.FLOOR
    )
    return min(floors, key=lambda p: (p[0] - center_x) ** 2 + (p[1] - center_y) ** 2)


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
    spawn_x, spawn_y = _spawn(tiles, config.map_width // 2, config.map_height // 2)
    agent = AgentState(x=spawn_x, y=spawn_y)
    seen: dict[tuple[int, int], int] = {}
    tick_count = 0
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
            tick_count += 1
            accumulator -= tick_duration
        fov = compute_fov(tiles, (agent.x, agent.y), config.fov_radius)
        for cell in fov:
            seen[cell] = tick_count
        cells = fog_grid(rows, palette, fov, seen, config.remembered_brightness)
        camera = (agent.x, agent.y)
        screen.draw_cells(cells, camera)
        screen.draw_glyph(config.agent_glyph, agent.x, agent.y, camera, config.agent_color)
        screen.present()
    screen.close()


if __name__ == "__main__":
    main()
