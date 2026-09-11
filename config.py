"""All tunables for AsciiCrawler, as one flat frozen dataclass."""

from dataclasses import dataclass, field


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
    # How many chunks across a biome region is. Four means a theme covers about
    # 256 tiles square - big enough to feel like a place, small enough that a
    # wander crosses several in a session.
    region_size: int = 4
    # How much darker the world gets with distance, at tier_distance_max. The
    # biome sets the hue; this keeps depth legible on top of it.
    depth_dimming: float = 0.22
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

    # Colour. Terrain stays low-saturation on purpose: it is the backdrop, and
    # anything competing with the agent, a monster or an item for attention is
    # working against the reader. One palette per biome, keyed by biome name.
    biome_colors: dict = field(
        default_factory=lambda: {
            # keys match world.biomes.BIOMES
            "halls": {"#": (158, 132, 96), ".": (82, 67, 47), "~": (72, 118, 170), "^": (208, 96, 48)},
            "caves": {"#": (98, 128, 150), ".": (46, 66, 82), "~": (64, 126, 196), "^": (216, 88, 44)},
            "caverns": {"#": (136, 88, 122), ".": (54, 36, 62), "~": (72, 96, 190), "^": (238, 92, 36)},
            # charcoal and ember: the lava is the terrain here
            "ashfields": {"#": (96, 72, 62), ".": (44, 32, 28), "~": (90, 96, 150), "^": (252, 104, 30)},
            # dry bone
            "ossuary": {"#": (178, 168, 142), ".": (84, 78, 64), "~": (86, 118, 150), "^": (214, 96, 46)},
            # bioluminescent damp
            "warren": {"#": (84, 132, 108), ".": (34, 58, 48), "~": (70, 168, 148), "^": (222, 104, 52)},
            # moss over old stone
            "ruins": {"#": (128, 134, 92), ".": (56, 62, 42), "~": (76, 128, 128), "^": (214, 98, 44)},
            # corroded iron and standing water
            "marsh": {"#": (134, 94, 62), ".": (58, 42, 30), "~": (78, 104, 82), "^": (226, 96, 40)},
            # pale facets
            "crystal": {"#": (152, 172, 204), ".": (56, 66, 88), "~": (96, 152, 220), "^": (220, 104, 60)},
            # glacial: bright rock, colder floor, ice paler than either
            "frozen": {"#": (176, 196, 214), ".": (62, 78, 96), "~": (86, 140, 200), "^": (214, 100, 56), "_": (206, 226, 240)},
            # sickly green murk
            "spores": {"#": (96, 116, 78), ".": (40, 52, 34), "~": (74, 122, 96), "^": (220, 108, 48), "*": (150, 210, 120)},
            # drowned stone
            "sunken": {"#": (104, 116, 130), ".": (60, 70, 82), "~": (52, 92, 134), "^": (206, 96, 52)},
            # steel and emergency lighting
            "station": {"#": (128, 142, 156), ".": (44, 52, 62), "~": (72, 118, 158), "^": (232, 120, 50)},
            # the inside of a machine
            "machine": {"#": (96, 128, 112), ".": (28, 40, 36), "~": (70, 130, 130), "^": (226, 110, 46)},
            # arcane lattice
            "weave": {"#": (150, 118, 190), ".": (48, 40, 66), "~": (96, 108, 200), "^": (224, 108, 62)},
        }
    )
    tile_jitter: float = 0.09  # +-9% per-tile brightness, hashed by position
    # How strongly each cell's background is washed with its terrain colour,
    # per fog tier. This is what carries the biome: a glyph is a couple of lit
    # pixels, so the ground has to do the work. Unknown stays black - the dark
    # is the point, and washing it would show rooms the agent has never seen.
    background_strength: dict = field(
        default_factory=lambda: {
            "visible": 0.44,
            "fresh": 0.26,
            "stale": 0.15,
        }
    )

    # Monsters run hotter as they get deadlier: a dragon should read as a
    # dragon before the watcher has parsed the letter.
    monster_colors: dict = field(
        default_factory=lambda: {
            "r": (150, 146, 140),
            "g": (120, 186, 116),
            "o": (186, 160, 78),
            "O": (214, 142, 84),
            "T": (190, 118, 206),
            "D": (236, 86, 74),
            "x": (150, 190, 170),
            "S": (120, 200, 220),
            "C": (110, 170, 235),
            "W": (170, 140, 245),
        }
    )
    item_colors: dict = field(
        default_factory=lambda: {
            ")": (206, 210, 224),
            "[": (150, 176, 208),
            "=": (232, 198, 116),
            '"': (204, 152, 224),
            "!": (124, 222, 186),
            "$": (240, 212, 94),
            "+": (136, 136, 148),
        }
    )

    # title screen
    soak_workers: int = 0  # 0 = one per core; used by the parallel soak runner
    # On death, keep the world (the creature starts again knowing where it has
    # been, and its gear is still on the floor) or roll a fresh one.
    new_world_on_death: bool = False
    soak_ticks: int = 3000  # per world, when soaking from the menu
    menu_title_font_size: int = 22  # the block letters get their own size
    menu_title_color: tuple[int, int, int] = (214, 170, 92)
    menu_text_color: tuple[int, int, int] = (206, 206, 216)
    menu_pick_color: tuple[int, int, int] = (250, 232, 160)
    menu_dim_color: tuple[int, int, int] = (116, 116, 132)

    # HUD and overlays
    hud_color: tuple[int, int, int] = (200, 200, 210)
    hud_dim_color: tuple[int, int, int] = (110, 110, 125)
    hud_accent_color: tuple[int, int, int] = (215, 180, 100)
    hud_good_color: tuple[int, int, int] = (120, 200, 130)
    hud_warn_color: tuple[int, int, int] = (220, 190, 90)
    hud_bad_color: tuple[int, int, int] = (220, 90, 90)
    hud_panel_width: int = 300
    hud_max_chars: int = 34  # HUD lines are clipped to this, longest gear names included
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
    # Hard ceiling on nodes one plan sweep may settle. Without it a single
    # unreachable candidate defeats the sweep's early stop - it never settles,
    # so the search runs to exhaustion over everything the agent remembers.
    # Anything beyond the cap scores about zero anyway: value is gain/(1+cost).
    path_expansion_cap: int = 3000
    # Stop a plan sweep once this many candidates have been reached. Dijkstra
    # settles them nearest first and score is gain/(1 + cost), so the ones it
    # stops short of were never going to win - and waiting for all of them
    # meant one unreachable candidate cost a full-cap sweep every time.
    plan_settle_target: int = 12
    # How far to look past a frontier tile to see what it opens onto, and how
    # much that counts next to the tiles immediately beyond it.
    frontier_lookahead: int = 4
    w_frontier_reach: float = 0.2
    # Distance counts against a target less than linearly, so new ground is
    # worth walking to rather than always losing to whatever is closest.
    explore_distance_falloff: float = 0.85
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

    # flourishes (Phase 7)
    chronicle_length: int = 8  # lines of recent history kept for the HUD
    lava_glow_radius: int = 3  # lava lights its surroundings, seen or not
    lava_heat_damage: int = 2  # standing next to lava hurts, per tick
    moss_chance: float = 0.06  # cosmetic floor tinting, seeded by position
    moss_color: tuple[int, int, int] = (90, 130, 95)
    ghost_rare_color: tuple[int, int, int] = (190, 160, 220)  # remembered loot
    ghost_danger_color: tuple[int, int, int] = (210, 120, 120)  # remembered threat

    # traps: hidden until spotted or sprung
    trap_glyph: str = "^"
    trap_damage: int = 6
    trap_detect_radius: int = 4  # tiles; a trap further off is never noticed
    trap_detect_chance: float = 0.25  # per tick, per trap in range
    # What a known trap adds to a step, in tiles of detour. Costly, never
    # forbidden: one remembered trap in a one-tile corridor used to wall the
    # agent off from the rest of its world for the rest of the run.
    hazard_step_cost: float = 12.0
    # Ice carries you on. Capped, because a long enough slide across a frozen
    # hall stops being a hazard and starts being teleportation.
    ice_slide_max: int = 3
    haze_damage: int = 2  # per tick spent standing in it
    haze_step_cost: float = 5.0  # what a plan pays to route through fog
    ice_step_cost: float = 2.0  # ...and what it pays to END a move on ice
    model_ice_slides: bool = True  # plan slides as physics, not as a penalty

    # Shrines: how often a chunk has one, and how far in before they appear.
    # Rare on purpose - a blessing you meet every other room is a stat, not an
    # event, and the point of walking to one is that it might be the bad kind.
    # Only back away from something at least this threatening. Retreating
    # from a rat reads as cowardice and never ends, because the rat follows.
    kite_threat_floor: float = 2.0
    shrine_color: tuple[int, int, int] = (198, 160, 224)  # totems, effigies, pillars
    shrine_chance: float = 0.45
    shrine_free_radius: int = 2  # chunks around spawn with none in them

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
    # After being cornered - frightened with nowhere calmer to go - stop asking
    # for this many ticks. Without it the agent stands down and re-triggers on
    # the very next tick, flickering in and out of flight while it works its
    # way out of a bad spot.
    flee_cornered_cooldown: int = 40
    # A flight that has run this long is not working - the agent is penned
    # between threats, or wearing something craven enough that it panics at
    # what it should be fighting. Give up, take the cooldown, do something.
    flee_max_ticks: int = 60

    # memory decay: knowledge expires, so the world goes unknown again
    memory_ttl: int = 3000  # ticks before a tile is forgotten outright
    memory_prune_interval: int = 250  # ticks between pruner sweeps
    memory_stale_fraction: float = 0.5  # age > ttl * this -> the stale tier

    # fog of war
    remembered_brightness: float = 0.72  # fresh memory
    stale_brightness: float = 0.5  # older than memory_stale_fraction of TTL
    # Remembered ground shifts toward this instead of only darkening. Most of
    # the screen is memory rather than sight, so dimming alone made the whole
    # world look unlit.
    memory_tint_color: tuple[int, int, int] = (74, 92, 132)
    fresh_tint: float = 0.30
    stale_tint: float = 0.52
    ghost_color: tuple[int, int, int] = (150, 150, 160)  # remembered entities


DEFAULT_CONFIG = Config()
