import dataclasses

import pytest

from config import DEFAULT_CONFIG, Config

INT_FIELDS = (
    "window_width",
    "window_height",
    "cell_size",
    "font_size",
    "max_fps",
    "map_width",
    "map_height",
    "map_seed",
    "bsp_min_partition",
    "bsp_min_room",
    "tps",
    "tick_seed",
    "fov_radius",
    "explore_throttle_ticks",
    "frontier_sample_size",
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
    assert DEFAULT_CONFIG.font_size == 15
    assert DEFAULT_CONFIG.map_width == 96
    assert DEFAULT_CONFIG.map_height == 54
    assert DEFAULT_CONFIG.tps == 10
    assert DEFAULT_CONFIG.max_fps > DEFAULT_CONFIG.tps
    assert DEFAULT_CONFIG.agent_glyph == "@"
    assert DEFAULT_CONFIG.fov_radius == 8
    assert DEFAULT_CONFIG.remembered_brightness == 0.6
    assert 0.0 < DEFAULT_CONFIG.remembered_brightness < 1.0
    assert DEFAULT_CONFIG.bsp_min_room + 2 <= DEFAULT_CONFIG.bsp_min_partition
    # agent brain tunables
    assert DEFAULT_CONFIG.w_explore > 0.0
    assert DEFAULT_CONFIG.explore_throttle_ticks >= 1
    assert DEFAULT_CONFIG.frontier_sample_size >= 1
    assert DEFAULT_CONFIG.explore_hysteresis_bonus >= 0.0
    assert 0.0 <= DEFAULT_CONFIG.explore_noise < DEFAULT_CONFIG.explore_hysteresis_bonus


def test_default_config_types():
    for name in INT_FIELDS:
        assert isinstance(getattr(DEFAULT_CONFIG, name), int), name
    assert isinstance(DEFAULT_CONFIG.max_frame_seconds, float)
    assert isinstance(DEFAULT_CONFIG.remembered_brightness, float)
    for name in ("w_explore", "explore_hysteresis_bonus", "explore_noise"):
        assert isinstance(getattr(DEFAULT_CONFIG, name), float), name
    assert isinstance(DEFAULT_CONFIG.font_path, str)
    assert isinstance(DEFAULT_CONFIG.window_title, str)
    for name in ("background_color", "wall_color", "floor_color", "agent_color"):
        color = getattr(DEFAULT_CONFIG, name)
        assert isinstance(color, tuple) and len(color) == 3, name


def test_glyph_fits_in_cell():
    assert DEFAULT_CONFIG.font_size <= DEFAULT_CONFIG.cell_size
