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

    # chunk world (infinite; the finite map is gone)
    world_seed: int = 4242
    chunk_size: int = 64
    preload_radius: int = 2  # chunks; generate when the agent comes this close
    # biome bands, in tiles from world origin (Euclidean at the chunk-center
    # tile, blended with +-band_blend_noise hashed noise so band edges dither
    # instead of forming hard rings)
    band_bsp_max: int = 150  # noised distance below this -> BSP rooms+corridors
    band_cavern_min: int = 400  # ...above this -> CA caverns with liquid pools
    band_blend_noise: float = 48.0
    seam_jitter: int = 8  # max offset of a seam crossing from the edge midpoint
    # BSP band (per chunk)
    bsp_min_partition: int = 12
    bsp_min_room: int = 4
    # cellular-automata caves (mid band) and caverns (far band)
    cave_fill_prob: float = 0.45
    cave_smooth_steps: int = 4
    cave_wall_threshold: int = 5  # walls among the 3x3 (incl. self) -> WALL
    cavern_fill_prob: float = 0.42
    cavern_smooth_steps: int = 5
    cavern_pool_chance: float = 0.5  # P(an attempt is taken), seeded
    cavern_pool_attempts: int = 4  # pond-growing attempts per chunk
    cavern_pool_min_size: int = 8  # pond size range, tiles
    cavern_pool_max_size: int = 40
    cavern_lava_share: float = 0.3  # P(LAVA | a pool forms), else WATER
    water_color: tuple[int, int, int] = (60, 120, 200)
    lava_color: tuple[int, int, int] = (220, 80, 40)

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
