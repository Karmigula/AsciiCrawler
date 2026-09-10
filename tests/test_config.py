import dataclasses

import pytest

from config import DEFAULT_CONFIG, Config

INT_FIELDS = (
    "window_width",
    "window_height",
    "cell_size",
    "font_size",
    "max_fps",
    "world_seed",
    "chunk_size",
    "preload_radius",
    "seam_jitter",
    "band_bsp_max",
    "band_cavern_min",
    "bsp_min_partition",
    "bsp_min_room",
    "cave_smooth_steps",
    "cave_wall_threshold",
    "cavern_smooth_steps",
    "cavern_pool_attempts",
    "cavern_pool_min_size",
    "cavern_pool_max_size",
    "tps",
    "tick_seed",
    "fov_radius",
    "explore_throttle_ticks",
    "frontier_sample_size",
)

FLOAT_FIELDS = (
    "band_blend_noise",
    "cave_fill_prob",
    "cavern_fill_prob",
    "cavern_pool_chance",
    "cavern_lava_share",
)


def test_default_config_is_a_config_instance():
    assert isinstance(DEFAULT_CONFIG, Config)


def test_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_CONFIG.tps = 20


def test_default_config_values():
    assert DEFAULT_CONFIG.window_width == 1200
    assert DEFAULT_CONFIG.window_height == 800
    assert DEFAULT_CONFIG.cell_size == 20
    assert DEFAULT_CONFIG.tps == 10
    assert DEFAULT_CONFIG.max_fps > DEFAULT_CONFIG.tps
    assert DEFAULT_CONFIG.agent_glyph == "@"
    assert DEFAULT_CONFIG.fov_radius == 8
    # Not pinned to an exact value: brightness is a matter of taste that gets
    # retuned. What must hold is the ordering - memory is dimmer than sight,
    # and stale memory dimmer than fresh.
    assert 0.0 < DEFAULT_CONFIG.stale_brightness < DEFAULT_CONFIG.remembered_brightness < 1.0
    assert DEFAULT_CONFIG.bsp_min_room + 2 <= DEFAULT_CONFIG.bsp_min_partition
    # agent brain tunables
    assert DEFAULT_CONFIG.w_explore > 0.0
    assert DEFAULT_CONFIG.explore_throttle_ticks >= 1
    assert DEFAULT_CONFIG.frontier_sample_size >= 1
    assert DEFAULT_CONFIG.explore_hysteresis_bonus >= 0.0
    assert 0.0 <= DEFAULT_CONFIG.explore_noise < DEFAULT_CONFIG.explore_hysteresis_bonus


def test_default_chunk_world_values():
    cfg = DEFAULT_CONFIG
    assert cfg.chunk_size == 64
    assert cfg.preload_radius == 2
    assert 0 < cfg.band_bsp_max < cfg.band_cavern_min  # BSP | caves | caverns
    assert cfg.band_blend_noise >= 0.0
    # seam crossings must stay on the shared edge, off its ends
    assert 2 * cfg.seam_jitter < cfg.chunk_size
    assert cfg.cavern_pool_min_size <= cfg.cavern_pool_max_size
    assert 0.0 <= cfg.cavern_pool_chance <= 1.0
    assert 0.0 <= cfg.cavern_lava_share <= 1.0


def test_default_config_types():
    for name in INT_FIELDS:
        assert isinstance(getattr(DEFAULT_CONFIG, name), int), name
    for name in FLOAT_FIELDS:
        assert isinstance(getattr(DEFAULT_CONFIG, name), float), name
    assert isinstance(DEFAULT_CONFIG.max_frame_seconds, float)
    assert isinstance(DEFAULT_CONFIG.remembered_brightness, float)
    for name in ("w_explore", "explore_hysteresis_bonus", "explore_noise"):
        assert isinstance(getattr(DEFAULT_CONFIG, name), float), name
    assert isinstance(DEFAULT_CONFIG.font_path, str)
    assert isinstance(DEFAULT_CONFIG.window_title, str)
    for name in (
        "background_color",
        "wall_color",
        "floor_color",
        "agent_color",
        "water_color",
        "lava_color",
    ):
        color = getattr(DEFAULT_CONFIG, name)
        assert isinstance(color, tuple) and len(color) == 3, name


def test_glyph_fits_in_cell():
    assert DEFAULT_CONFIG.font_size <= DEFAULT_CONFIG.cell_size


def test_phase_3_population_and_decay_tunables_are_present_and_sane():
    """Every Phase 3 knob lives in config, not scattered as literals."""
    cfg = DEFAULT_CONFIG
    assert 0 < cfg.spawn_density_near < cfg.spawn_density_far < 1
    assert cfg.item_density > 0 and cfg.trap_density > 0
    assert cfg.tier_distance_max > 0
    assert cfg.activation_radius > 0
    assert cfg.respawn_cooldown_ticks > 0 and cfg.respawn_cap_per_chunk > 0
    assert cfg.memory_ttl > cfg.memory_prune_interval > 0
    assert 0 < cfg.memory_stale_fraction < 1


def test_the_fog_tiers_dim_in_order():
    cfg = DEFAULT_CONFIG
    assert 1.0 > cfg.remembered_brightness > cfg.stale_brightness > 0.0
