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
    "tps",
    "tick_seed",
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


def test_default_config_types():
    for name in INT_FIELDS:
        assert isinstance(getattr(DEFAULT_CONFIG, name), int), name
    assert isinstance(DEFAULT_CONFIG.max_frame_seconds, float)
    assert isinstance(DEFAULT_CONFIG.font_path, str)
    assert isinstance(DEFAULT_CONFIG.window_title, str)
    for name in ("background_color", "wall_color", "floor_color", "agent_color"):
        color = getattr(DEFAULT_CONFIG, name)
        assert isinstance(color, tuple) and len(color) == 3, name


def test_glyph_fits_in_cell():
    assert DEFAULT_CONFIG.font_size <= DEFAULT_CONFIG.cell_size
