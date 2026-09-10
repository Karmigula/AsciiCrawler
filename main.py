"""Wiring, fixed-timestep game loop, and the watcher's controls.

The loop only orchestrates: ticks advance the agent through the infinite chunk
world, then rendering hands the screen a world-window of glyph rows around the
camera (built through `tile_at`), shades it through the same memory the brain
uses, optionally recolours it through a debug overlay, and draws the agent and
the HUD on top. No decisions are made here.

The window opens on the title screen; `esc` goes back to it from the world,
and `esc` again closes the game. The creature keeps running while the menu is
up - it is paused, not discarded, so "resume" resumes.

Controls
    esc        back to the title screen (and from there, quit)
    space      pause
    1 2 3      speed 1x / 4x / 16x
    F1..F5     overlays: fov, memory age, threat, plan, frontier
    h          toggle the HUD
    F10        borderless window
    F11        borderless fullscreen
    n          new world (fresh seed, fresh creature)
    p          screenshot

Speed multiplies ticks per frame rather than shortening the frame, so 16x is
the same simulation run faster and not a different one.
"""

import random
from datetime import datetime
from pathlib import Path

import pygame

from agent.fov import compute_fov
from config import DEFAULT_CONFIG, Config
from render.fog import fog_grid
from render.hud import chronicle_lines, equipment_lines, help_lines, hud_lines
from render.menu import ENTRIES, TITLE_ROWS, menu_lines, move_selection
from render.flourish import speckle_moss
from render.palette import background_grid, item_color, monster_color, terrain_color
from render.overlays import OVERLAY_NAMES, apply_overlay
from render.screen import Screen
from sim.tick import AgentState, tick
from world.chunks import ChunkStore
from world.tiles import Tile

_OVERLAY_KEYS = {
    pygame.K_F1: OVERLAY_NAMES[0],
    pygame.K_F2: OVERLAY_NAMES[1],
    pygame.K_F3: OVERLAY_NAMES[2],
    pygame.K_F4: OVERLAY_NAMES[3],
    pygame.K_F5: OVERLAY_NAMES[4],
}


def _new_world(config: Config, seed: int):
    """A fresh world and a fresh creature to live in it."""
    world = ChunkStore(config, world_seed=seed)
    spawn = world.spawn
    return world, AgentState(x=spawn[0], y=spawn[1]), random.Random(seed + 1)


def main(config: Config = DEFAULT_CONFIG) -> None:
    seed = config.world_seed
    world, agent, rng = None, None, None
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
    speed_index = 0
    paused = False
    overlay = None
    show_hud = True
    running = True
    in_menu = True
    selected = 0

    while running:
        dt = clock.tick(config.max_fps) / 1000.0
        accumulator = min(accumulator + dt, config.max_frame_seconds)

        if in_menu:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen.resize(event.size)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        screen.toggle_fullscreen()
                    elif event.key == pygame.K_F10:
                        screen.toggle_borderless()
                    elif event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        selected = move_selection(selected, -1)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        selected = move_selection(selected, 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        choice = ENTRIES[selected][0]
                        if choice == "quit":
                            running = False
                        else:
                            if choice == "new world" or agent is None:
                                if choice == "new world" and agent is not None:
                                    seed += 1
                                world, agent, rng = _new_world(config, seed)
                            accumulator = 0.0
                            in_menu = False
            screen.draw_centered(
                menu_lines(selected, seed, config, agent is not None),
                big_lines=TITLE_ROWS,
            )
            screen.present()
            continue

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen.resize(event.size)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    screen.toggle_fullscreen()
                elif event.key == pygame.K_F10:
                    screen.toggle_borderless()
                elif event.key == pygame.K_ESCAPE:
                    in_menu = True  # back to the title screen, not out of the game
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    speed_index = min(
                        (pygame.K_1, pygame.K_2, pygame.K_3).index(event.key),
                        len(config.speed_steps) - 1,
                    )
                elif event.key in _OVERLAY_KEYS:
                    chosen = _OVERLAY_KEYS[event.key]
                    overlay = None if overlay == chosen else chosen
                elif event.key == pygame.K_h:
                    show_hud = not show_hud
                elif event.key == pygame.K_n:
                    seed += 1
                    world, agent, rng = _new_world(config, seed)
                    accumulator = 0.0
                elif event.key == pygame.K_p:
                    _save_screenshot(screen, config, seed, agent)

        speed = config.speed_steps[speed_index]
        while accumulator >= tick_duration:
            if not paused:
                for _ in range(speed):
                    tick(agent, world, rng, config)
            accumulator -= tick_duration

        camera = (agent.x, agent.y)
        origin = screen.camera_origin(camera)
        cols, rows = screen.view_dims
        rows_text = [
            "".join(
                world.tile_at(origin[0] + x, origin[1] + y).glyph for x in range(cols)
            )
            for y in range(rows)
        ]
        visible = _fov_global(world, agent, config)
        mind = agent.mind(config)
        cells = fog_grid(
            rows_text,
            palette,
            visible,
            agent.memory,
            config.remembered_brightness,
            origin=origin,
            tick=agent.tick_count,
            ttl=mind.memory_ttl,
            stale_factor=config.stale_brightness,
            stale_fraction=config.memory_stale_fraction,
            ghost_color=config.ghost_color,
            color_for=lambda glyph, coord: terrain_color(glyph, coord, config),
            ghost_color_for=lambda glyph: _thing_color(glyph, config),
            memory_tint=config.memory_tint_color,
            fresh_tint=config.fresh_tint,
            stale_tint=config.stale_tint,
        )
        cells = speckle_moss(cells, origin, Tile.FLOOR.glyph, config)
        if overlay is not None:
            cells = apply_overlay(cells, overlay, origin, agent, visible, mind)
        screen.draw_cells(
            cells,
            background_grid(
                rows_text,
                origin,
                visible,
                agent.memory,
                config,
                tick=agent.tick_count,
                ttl=mind.memory_ttl,
            ),
        )
        screen.draw_glyph(
            config.agent_glyph, agent.x, agent.y, camera, config.agent_color
        )
        if show_hud:
            screen.draw_panel(hud_lines(agent, len(world), config, speed, paused))
            screen.draw_panel(chronicle_lines(agent, config), right=False, top=False)
            screen.draw_panel(
                equipment_lines(agent, config) + [("", config.hud_color)] + help_lines(config),
                right=True,
                top=False,
            )
        screen.present()
    screen.close()


def _thing_color(glyph: str, config: Config):
    """Whatever is standing on a tile: monsters by threat, items by kind."""
    if glyph in config.monster_colors:
        return monster_color(glyph, config)
    return item_color(glyph, config)


def _save_screenshot(screen: Screen, config: Config, seed: int, agent: AgentState) -> None:
    folder = Path(config.screenshot_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    screen.screenshot(folder / f"crawler-{seed}-{agent.tick_count}-{stamp}.png")


def _fov_global(world: ChunkStore, agent: AgentState, config: Config) -> set[tuple[int, int]]:
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


if __name__ == "__main__":
    main()
