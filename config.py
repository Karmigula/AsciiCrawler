"""All tunables for AsciiCrawler, as one flat frozen dataclass."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # window / presentation
    window_title: str = "asciicrawler"
    window_width: int = 1200
    window_height: int = 800
    cell_size: int = 20
    font_size: int = 15
    font_path: str = "assets/fonts/IBMPlexMono-Regular.ttf"
    background_color: tuple[int, int, int] = (12, 12, 16)
    wall_color: tuple[int, int, int] = (170, 170, 180)
    floor_color: tuple[int, int, int] = (85, 85, 95)
    agent_color: tuple[int, int, int] = (240, 240, 245)
    max_fps: int = 60

    # world
    map_width: int = 96
    map_height: int = 54
    map_seed: int = 4242
    bsp_min_partition: int = 12
    bsp_min_room: int = 4

    # simulation
    tps: int = 10
    tick_seed: int = 1337
    max_frame_seconds: float = 0.25

    # agent
    agent_glyph: str = "@"
    fov_radius: int = 8

    # agent brain: EXPLORE utility goal
    w_explore: float = 1.0
    explore_throttle_ticks: int = 5
    frontier_sample_size: int = 50
    explore_hysteresis_bonus: float = 0.1
    explore_noise: float = 0.02

    # fog of war
    remembered_brightness: float = 0.6


DEFAULT_CONFIG = Config()
