"""Settings that survive a restart, and reach the soak runner."""

import json

import pytest

import settings_store
from config import DEFAULT_CONFIG
from render.menu import (
    apply_settings,
    apply_stored,
    default_settings,
    soak_lines,
    stored_values,
)


@pytest.fixture
def store(tmp_path):
    return tmp_path / "settings.json"


def test_settings_survive_a_round_trip(store):
    settings = default_settings(DEFAULT_CONFIG, 8)
    settings[0].index = 2  # three workers
    settings_store.save_values(stored_values(settings), store)

    restored = default_settings(DEFAULT_CONFIG, 8)
    apply_stored(restored, settings_store.load_values(store))

    assert stored_values(restored) == stored_values(settings)
    assert restored[0].value == 3


def test_a_missing_file_is_just_the_first_run(tmp_path):
    assert settings_store.load_values(tmp_path / "nothing.json") == {}


def test_a_corrupt_file_does_not_stop_anything(store):
    store.write_text("{this is not json", encoding="utf-8")
    assert settings_store.load_values(store) == {}


def test_a_file_holding_the_wrong_shape_is_ignored(store):
    store.write_text("[1, 2, 3]", encoding="utf-8")
    assert settings_store.load_values(store) == {}


def test_stale_values_are_skipped_rather_than_forced(store):
    """A worker count from a bigger machine must not put the menu into a state
    it cannot show."""
    settings_store.save_values({"workers": 999, "moss": False}, store)
    settings = default_settings(DEFAULT_CONFIG, 4)
    apply_stored(settings, settings_store.load_values(store))

    assert settings[0].value <= 4, "the impossible worker count was ignored"
    moss = next(s for s in settings if s.key == "moss")
    assert moss.value is False, "the possible one was kept"


def test_what_is_written_is_readable_json(store):
    settings_store.save_values(stored_values(default_settings(DEFAULT_CONFIG, 4)), store)
    written = json.loads(store.read_text(encoding="utf-8"))
    assert "workers" in written and "on_death" in written


def test_the_soak_runner_uses_the_saved_worker_count(store, monkeypatch):
    """The disconnect this file exists to fix: the menu used to write the
    worker count into a config object that nothing outside the session read."""
    settings_store.save_values({"workers": 3}, store)
    monkeypatch.setattr(settings_store, "DEFAULT_PATH", store)

    from sim.soak import configured_workers

    assert configured_workers() == 3


def test_the_soak_runner_falls_back_when_nothing_is_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "DEFAULT_PATH", tmp_path / "none.json")

    from sim.soak import available_workers, configured_workers

    assert configured_workers() == available_workers()


def test_death_behaviour_reaches_the_config():
    settings = default_settings(DEFAULT_CONFIG, 4)
    death = next(s for s in settings if s.key == "on_death")
    assert apply_settings(settings, DEFAULT_CONFIG).new_world_on_death is False
    death.index = death.values.index("new world")
    assert apply_settings(settings, DEFAULT_CONFIG).new_world_on_death is True


def test_a_new_world_is_rolled_only_when_asked_and_only_on_a_new_death():
    from dataclasses import replace

    from main import should_restart

    staying = replace(DEFAULT_CONFIG, new_world_on_death=False)
    leaving = replace(DEFAULT_CONFIG, new_world_on_death=True)

    assert should_restart(leaving, 1, 0) is True
    assert should_restart(leaving, 1, 1) is False, "the same death twice"
    assert should_restart(leaving, 0, 0) is False
    assert should_restart(staying, 5, 0) is False, "not asked for"


def test_the_soak_screen_flags_a_world_that_went_wrong():
    from sim.harness import SimStats

    def world(seed, starved, moved):
        return SimStats(
            ticks=1000, seed=seed, chunks_generated=10, max_distance=100,
            moved_ticks=moved, memory_tiles=100, memory_peak=100, pruned_tiles=1,
            monsters_seen=1, frontier_starved_ticks=starved, decisions=1, flights=0,
            pickups=1, gold=0, archetype="scout", traps_found=0, traps_sprung=0,
            kills=1, deaths=0, damage_taken=0, final_level=1, final_position=(0, 0),
        )

    healthy = world(1, 0, 990)
    starving = world(2, 900, 990)
    frozen = world(3, 0, 10)
    lines = soak_lines("done", [healthy, starving, frozen], DEFAULT_CONFIG)
    colours = {text: colour for text, colour in lines}

    good = next(c for t, c in colours.items() if t.startswith("seed 1"))
    bad = next(c for t, c in colours.items() if t.startswith("seed 2"))
    stalled = next(c for t, c in colours.items() if t.startswith("seed 3"))
    assert bad == DEFAULT_CONFIG.hud_bad_color, "a starving world is flagged"
    assert stalled == DEFAULT_CONFIG.hud_bad_color, "so is one that stopped moving"
    assert good != DEFAULT_CONFIG.hud_bad_color
