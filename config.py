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

    # HUD and overlays
    hud_color: tuple[int, int, int] = (200, 200, 210)
    hud_dim_color: tuple[int, int, int] = (110, 110, 125)
    hud_accent_color: tuple[int, int, int] = (215, 180, 100)
    hud_good_color: tuple[int, int, int] = (120, 200, 130)
    hud_warn_color: tuple[int, int, int] = (220, 190, 90)
    hud_bad_color: tuple[int, int, int] = (220, 90, 90)
    hud_panel_width: int = 300
    hud_line_height: int = 18
    overlay_hot_color: tuple[int, int, int] = (250, 240, 140)
    overlay_cold_color: tuple[int, int, int] = (70, 90, 140)
    overlay_danger_color: tuple[int, int, int] = (240, 80, 80)
    overlay_plan_color: tuple[int, int, int] = (120, 220, 220)
    speed_steps: tuple[int, ...] = (1, 4, 16)
    screenshot_dir: str = "screenshots"

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

    # population (Phase 3 places data only; AI, combat and traps fire in Phase 4)
    spawn_density_near: float = 0.002  # monsters per floor tile at the origin
    spawn_density_far: float = 0.008  # ...once tier_distance_max is reached
    item_density: float = 0.003  # items per floor tile (flat; loot is Phase 5)
    trap_density: float = 0.0015  # hidden traps per floor tile
    tier_distance_max: int = 900  # distance at which the deepest table unlocks
    activation_radius: int = 40  # tiles; entities outside are inert data
    respawn_cooldown_ticks: int = 1500  # per chunk, once the agent is far
    respawn_cap_per_chunk: int = 24  # Phase 4 respawn ceiling, not a spawn cap

    # monster behaviour (Phase 4). Speed is ticks-per-move, so a monster acts
    # on ticks where tick % speed == 0: speed 1 every tick, speed 2 every other.
    monster_sight_radius: int = 9  # Chebyshev; inside it a monster gives chase
    monster_wander_chance: float = 0.6  # P(an idle monster steps at all)

    # the agent as a creature that can die (Phase 4)
    agent_max_hp: int = 30
    agent_attack: int = 5
    agent_defense: int = 1
    damage_variance: int = 2  # 0..this is added to every blow, seeded
    monster_drop_chance: float = 0.35  # P(a corpse leaves something behind)
    grave_glyph: str = "+"

    # experience and growth
    xp_per_tier: int = 8  # a kill is worth (tier + 1) * this
    xp_level_base: int = 30  # xp from level 1 to level 2
    xp_level_growth: float = 1.6  # each level costs this much more than the last
    level_hp_gain: int = 6
    level_attack_gain: int = 1

    # respawn: a cleared chunk refills once the agent is well away from it
    respawn_distance: int = 60  # tiles; nearer than this and nothing respawns
    respawn_check_interval: int = 100  # ticks between respawn sweeps

    # loot: affixes and how nasty the rolls get
    curse_chance: float = 0.22  # P(an affix slot rolls a curse instead)

    # how the agent prices a loadout. These weights are what an "archetype"
    # is made of: change them and the creature starts wanting different gear.
    v_attack: float = 1.0
    v_defense: float = 1.2
    v_max_hp: float = 0.25
    v_fov: float = 1.5  # a wider view is worth a lot to something exploring
    v_memory: float = 0.0008  # per tick of TTL
    v_explore: float = 2.0
    v_trigger: float = 0.8  # per point of trigger amount
    v_flee_penalty: float = 0.5  # recklessness is priced, not free
    equip_margin: float = 0.5  # score gain needed to bother swapping gear
    potion_heal: int = 12
    potion_at_hp_fraction: float = 0.45  # drink when this hurt, not before
    w_loot: float = 1.4  # how loud a remembered item calls
    loot_expectation: float = 3.0  # assumed upgrade from an unknown slot item
    backpack_size: int = 6

    # traps: hidden until spotted or sprung
    trap_glyph: str = "^"
    trap_damage: int = 6
    trap_detect_radius: int = 4  # tiles; a trap further off is never noticed
    trap_detect_chance: float = 0.25  # per tick, per trap in range

    # fear: threat read off memory, never off world truth
    threat_radius: int = 10  # tiles; remembered monsters further out are ignored
    w_threat: float = 2.5  # how hard threat discounts an EXPLORE candidate
    # 1.5 at full health means: fight rats, goblins and orcs; keep away from a
    # troll within 2 tiles and a dragon within 4. Scaled by hp, so a wounded
    # agent runs from things it would have swung at.
    flee_threat: float = 1.5
    flee_search_radius: int = 7  # how far FLEE looks for a safer tile
    # Stop fleeing below this fraction of the trigger. 0.6 produced flicker:
    # 235 flights averaging 2.2 ticks over 3000, the agent bouncing off the
    # same monster again and again. 0.35 gives 3 flights averaging 18 ticks
    # and half again as many kills - fewer, longer, legible flights.
    flee_release: float = 0.35

    # memory decay: knowledge expires, so the world goes unknown again
    memory_ttl: int = 3000  # ticks before a tile is forgotten outright
    memory_prune_interval: int = 250  # ticks between pruner sweeps
    memory_stale_fraction: float = 0.5  # age > ttl * this -> the stale tier

    # fog of war
    remembered_brightness: float = 0.6  # fresh memory
    stale_brightness: float = 0.35  # older than memory_stale_fraction of TTL
    ghost_color: tuple[int, int, int] = (150, 150, 160)  # remembered entities


DEFAULT_CONFIG = Config()
