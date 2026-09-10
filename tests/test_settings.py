"""The settings screen."""

from config import DEFAULT_CONFIG
from render.menu import adjust, apply_settings, default_settings, settings_lines


def _settings(workers: int = 8):
    return default_settings(DEFAULT_CONFIG, workers)


def test_workers_comes_first_because_it_is_the_machine_dependent_one():
    assert _settings()[0].key == "workers"


def test_worker_choices_span_the_machine():
    settings = _settings(8)
    assert settings[0].values[0] == 1
    assert settings[0].values[-1] == 8
    assert settings[0].value == 8, "defaults to using the whole machine"


def test_a_single_core_machine_still_offers_a_choice():
    settings = default_settings(DEFAULT_CONFIG, 1)
    assert len(settings[0].values) >= 1
    assert settings[0].value >= 1


def test_adjusting_steps_through_the_choices_and_stops_at_the_ends():
    settings = _settings()
    settings[0].index = 0
    adjust(settings, 0, -1)
    assert settings[0].index == 0, "clamped at the bottom"
    for _ in range(50):
        adjust(settings, 0, 1)
    assert settings[0].index == len(settings[0].values) - 1, "clamped at the top"


def test_the_screen_shows_every_setting_with_its_value():
    settings = _settings()
    body = "\n".join(text for text, _ in settings_lines(settings, 0, DEFAULT_CONFIG))
    for setting in settings:
        assert setting.label in body
        assert setting.shown() in body


def test_only_the_selected_setting_is_marked():
    settings = _settings()
    for index in range(len(settings)):
        marked = [
            text
            for text, _ in settings_lines(settings, index, DEFAULT_CONFIG)
            if text.startswith(">")
        ]
        assert len(marked) == 1
        assert settings[index].label in marked[0]


def test_turning_moss_off_actually_turns_it_off():
    settings = _settings()
    moss = next(i for i, s in enumerate(settings) if s.key == "moss")
    adjust(settings, moss, 1)
    assert apply_settings(settings, DEFAULT_CONFIG).moss_chance == 0.0


def test_the_colour_wash_carries_through_to_every_fog_tier():
    settings = _settings()
    wash = next(i for i, s in enumerate(settings) if s.key == "wash")
    settings[wash].index = len(settings[wash].values) - 1
    applied = apply_settings(settings, DEFAULT_CONFIG)
    strengths = applied.background_strength
    assert strengths["visible"] == settings[wash].value
    assert strengths["visible"] > strengths["fresh"] > strengths["stale"], (
        "remembered ground must stay dimmer than seen ground"
    )


def test_the_worker_setting_reaches_the_config():
    settings = _settings(8)
    settings[0].index = 3  # four workers
    assert apply_settings(settings, DEFAULT_CONFIG).soak_workers == 4


def test_applying_settings_leaves_the_rest_of_the_config_alone():
    applied = apply_settings(_settings(), DEFAULT_CONFIG)
    assert applied.chunk_size == DEFAULT_CONFIG.chunk_size
    assert applied.memory_ttl == DEFAULT_CONFIG.memory_ttl
    assert applied.flee_threat == DEFAULT_CONFIG.flee_threat
