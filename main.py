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
    b          show what is in the bag
    j          what every symbol means
    h          toggle the HUD
    F10        borderless window
    F11        borderless fullscreen
    n          new world (fresh seed, fresh creature)
    p          screenshot

Speed multiplies ticks per frame rather than shortening the frame, so 16x is
the same simulation run faster and not a different one.
"""

import random
import sys
from datetime import datetime

from pathlib import Path

import pygame

from config import DEFAULT_CONFIG, Config
from paths import FROZEN, beside, bundled, note
from render.frame import boss_in_view, build_frame
from render.hud import (
    bag_lines,
    chronicle_lines,
    equipment_lines,
    help_lines,
    hud_lines,
)
import settings_store
from render.menu import (
    ENTRIES,
    TITLE_ROWS,
    adjust,
    block_text,
    apply_settings,
    apply_stored,
    default_settings,
    menu_lines,
    move_selection,
    hall_lines,
    settings_lines,
    soak_lines,
    stored_values,
)
from sim import hall
from render.legend import legend_rows
from render.packs import EMPTY, discover, load as load_pack
from render.overlays import OVERLAY_NAMES
from render.screen import Screen
from sim.session import should_restart
from sim.soak import available_workers, run_many
from sim.tick import AgentState, tick
from world.chunks import ChunkStore

_OVERLAY_KEYS = {
    pygame.K_F1: OVERLAY_NAMES[0],
    pygame.K_F2: OVERLAY_NAMES[1],
    pygame.K_F3: OVERLAY_NAMES[2],
    pygame.K_F4: OVERLAY_NAMES[3],
    pygame.K_F5: OVERLAY_NAMES[4],
}


def _dress(screen, config: Config) -> None:
    """Put the chosen texture pack on the screen, or take it off.

    Loaded on the way in and again whenever the setting changes, because a
    pack is a folder somebody can edit while the game is running and the
    friendliest time to find out it is broken is immediately.

    Anything wrong with it is printed and then ignored: the glyphs it got
    right are drawn and the rest stay as letters, which is the same rule that
    applies to a pack that simply does not mention them.
    """
    if not config.texture_pack:
        screen.use_pack(EMPTY)
        return
    pack = load_pack(beside(config.pack_dir) / config.texture_pack)
    for problem in screen.use_pack(pack):
        note(f"texture pack: {problem}")


def _new_world(config: Config, seed: int):
    """A fresh world and a fresh creature to live in it."""
    world = ChunkStore(config, world_seed=seed)
    spawn = world.spawn
    return world, AgentState(x=spawn[0], y=spawn[1]), random.Random(seed + 1)


def main(config: Config = DEFAULT_CONFIG) -> None:
    seed = config.world_seed
    world, agent, rng = None, None, None
    screen = Screen(config)
    clock = pygame.time.Clock()
    tick_duration = 1.0 / config.tps
    accumulator = 0.0
    speed_index = 0
    paused = False
    overlay = None
    show_hud = True
    show_bag = False
    running = True
    in_menu = True
    in_settings = False
    selected = 0
    setting_selected = 0
    settings = default_settings(config, available_workers())
    apply_stored(settings, settings_store.load_values())
    config = apply_settings(settings, config)
    _dress(screen, config)
    speed_index = _speed_index_for(settings, config)
    soak_results = None
    soaking = False
    in_hall = False
    hall_entries = hall.load()
    in_legend = False
    deaths_seen = 0

    while running:
        dt = clock.tick(config.max_fps) / 1000.0
        accumulator = min(accumulator + dt, config.max_frame_seconds)

        if in_legend:
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
                    elif event.key in (pygame.K_j, pygame.K_ESCAPE):
                        in_legend = False
            screen.draw_legend(legend_rows(config), config, block_text("LEGEND"))
            screen.present()
            continue

        if in_hall:
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
                        in_hall = False
            # Four lines of chrome around the table: a blank, the column
            # headings, another blank and the way out.
            room = screen.centered_capacity(big_lines=5, reserved=4)
            screen.draw_centered(
                hall_lines(hall_entries, config, limit=room), big_lines=5
            )
            screen.present()
            continue

        if soaking:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen.resize(event.size)
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    soaking = False
            if soak_results is None:
                workers = config.soak_workers or available_workers()
                screen.draw_centered(
                    soak_lines(
                        f"running {workers} worlds x {config.soak_ticks} ticks"
                        " - the window will not respond until they finish",
                        None,
                        config,
                    ),
                    big_lines=5,
                )
                screen.present()
                soak_results = run_many(
                    config.soak_ticks,
                    list(range(1, workers + 1)),
                    config,
                    workers=workers,
                )
            screen.draw_centered(
                soak_lines(
                    f"{len(soak_results)} worlds, {config.soak_ticks} ticks each",
                    soak_results,
                    config,
                ),
                big_lines=5,
            )
            screen.present()
            continue

        if in_settings:
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
                        in_settings = False
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        setting_selected = (setting_selected - 1) % len(settings)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        setting_selected = (setting_selected + 1) % len(settings)
                    elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                        step = -1 if event.key in (pygame.K_LEFT, pygame.K_a) else 1
                        adjust(settings, setting_selected, step)
                        config = apply_settings(settings, config)
                        speed_index = _speed_index_for(settings, config)
                        _dress(screen, config)
                        settings_store.save_values(stored_values(settings))
            screen.draw_centered(
                settings_lines(settings, setting_selected, config), big_lines=5
            )
            screen.present()
            continue

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
                    elif event.key == pygame.K_j:
                        in_legend = True
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        choice = ENTRIES[selected][0]
                        if choice == "quit":
                            running = False
                        elif choice == "settings":
                            in_settings = True
                        elif choice == "soak":
                            soaking = True
                            soak_results = None
                        elif choice == "hall of fame":
                            hall_entries = hall.load()
                            in_hall = True
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
                elif event.key == pygame.K_j:
                    in_legend = True
                elif event.key == pygame.K_b:
                    show_bag = not show_bag
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

        while agent.fallen:
            # The tick records lives; writing them down is this loop's job,
            # which keeps sim/ free of file handling.
            hall_entries = hall.remember(agent.fallen.pop(0))

        if should_restart(config, agent.deaths, deaths_seen):
            # Death is where a run ends, if that is how it has been set up:
            # a new seed rather than the same dungeon with the body's gear
            # still lying in it.
            seed += 1
            world, agent, rng = _new_world(config, seed)
            deaths_seen = 0
            accumulator = 0.0
            continue
        deaths_seen = agent.deaths

        camera = (agent.x, agent.y)
        origin = screen.camera_origin(camera)
        cols, rows = screen.view_dims
        shades: list = []
        biomes: list = []
        cells, backgrounds, _ = build_frame(
            world,
            agent,
            config,
            origin,
            cols,
            rows,
            overlay,
            shades_out=shades,
            biomes_out=biomes,
        )
        screen.draw_cells(cells, backgrounds, shades, biomes)
        screen.draw_glyph(
            config.agent_glyph, agent.x, agent.y, camera, config.agent_color
        )
        if show_hud:
            here = world.biome_at(agent.x, agent.y)
            screen.draw_panel(
                hud_lines(
                    agent,
                    len(world),
                    config,
                    speed,
                    paused,
                    biome=(here.key, here.label),
                    boss=boss_in_view(world, agent, config),
                )
            )
            # Both, not one or the other: they sit in different corners, and
            # the bag was never a reason to stop telling you what just
            # happened. The bag yields if the window is too short for both.
            recent = chronicle_lines(agent, config)
            screen.draw_panel(recent, right=False, top=False)
            if show_bag:
                room = screen.panel_capacity(len(recent))
                screen.draw_panel(bag_lines(agent, config)[:room], right=False, top=True)
            screen.draw_panel(
                equipment_lines(agent, config) + [("", config.hud_color)] + help_lines(config),
                right=True,
                top=False,
            )
        screen.present()
    screen.close()


def _speed_index_for(settings, config: Config) -> int:
    """Which speed step the settings screen currently names."""
    for setting in settings:
        if setting.key == "speed":
            steps = list(config.speed_steps)
            return steps.index(setting.value) if setting.value in steps else 0
    return 0


def _save_screenshot(screen: Screen, config: Config, seed: int, agent: AgentState) -> None:
    # Beside the game: a screenshot saved inside a frozen build's temporary
    # unpack folder would be deleted the moment the player closed the window.
    folder = beside(config.screenshot_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    screen.screenshot(folder / f"crawler-{seed}-{agent.tick_count}-{stamp}.png")


def self_check(config: Config = DEFAULT_CONFIG, report=None) -> int:
    """Start everything, draw one frame, say what was found, and stop.

    This is for the frozen build. The two things freezing breaks are the font
    and the texture packs - both are found by path, and both fail quietly:
    a missing font falls back to pygame's default and a missing pack folder
    just means no packs in the settings screen. Neither crashes, so neither
    would be noticed before somebody downloaded the zip.
    """
    screen = Screen(config)
    world, agent, _rng = _new_world(config, config.world_seed)
    origin = screen.camera_origin((agent.x, agent.y))
    cols, rows = screen.view_dims
    cells, backgrounds, _ = build_frame(world, agent, config, origin, cols, rows)
    screen.draw_cells(cells, backgrounds)

    font = bundled(config.font_path)
    packs = sorted(folder.name for folder in discover(beside(config.pack_dir)))
    drawn = sum(1 for line in cells for cell in line if cell is not None)

    lines = [
        f"frozen: {FROZEN}",
        f"font: {font} {'found' if font.is_file() else 'MISSING'}",
        f"packs: {beside(config.pack_dir)} -> {packs or 'none'}",
        f"settings: {settings_store.DEFAULT_PATH}",
        f"hall: {hall.DEFAULT_PATH}",
        f"drew {drawn} cells",
    ]
    for line in lines:
        note(line)
    if report is not None:
        # A windowed build has no stdout at all, so the only way it can tell
        # anybody what it found is to write it down. `tools/check_release.py`
        # hands in the path and reads this back.
        try:
            Path(report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as reason:
            note(f"could not write {report}: {reason}")
            return 1

    if not font.is_file():
        return 1
    if not packs:
        return 1
    # The three things the player owns have to be somewhere they can see and
    # somewhere that survives the exe being replaced - which means beside it,
    # never inside the temporary folder a frozen build unpacks itself into.
    home = beside(".").resolve()
    for owned in (settings_store.DEFAULT_PATH, hall.DEFAULT_PATH):
        if Path(owned).resolve().parent != home:
            note(f"{owned} is not beside the game")
            return 1
    # A freshly spawned creature has only its own field of view painted and
    # the rest of the window is legitimately blank, so this is a floor on
    # "something was drawn at all", not a fraction of the screen.
    if drawn < 40:
        return 1
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        # Used by the release workflow against the built exe. The optional
        # path after it is where to write the report, because a windowed
        # build has nowhere to print one.
        rest = sys.argv[sys.argv.index("--check") + 1 :]
        sys.exit(self_check(report=rest[0] if rest else None))
    if "--soak" in sys.argv:
        # Delegated rather than duplicated, and it says where the real entry
        # point is: worker processes re-import this module under Windows
        # spawn, so soaking through the game costs a pygame startup per worker.
        print("tip: python -m sim.soak <ticks> <worlds> <workers> avoids loading pygame")
        from sim.soak import main as soak_main

        soak_main(sys.argv[sys.argv.index("--soak") + 1 :])
    else:
        main()
