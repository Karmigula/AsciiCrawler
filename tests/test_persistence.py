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


def test_a_hall_can_be_written_somewhere_that_does_not_exist_yet(tmp_path):
    """A mounted volume starts empty, and this failure is a silent one.

    `save` swallows OSError on purpose - losing a scoreboard is not worth a
    crash - so writing into a missing folder recorded nothing, reported
    nothing, and left a hall that stayed empty for good.
    """
    from sim import hall
    from sim.hall import Fallen

    where = tmp_path / "volume" / "nested" / "hall_of_fame.json"
    entry = Fallen(
        seed=1, level=4, kills=9, depth=120, ticks=800,
        killer="a troll", archetype="scout", gold=3, name="Someone Ashwake",
    )

    assert hall.save([entry], where) is True, "the write reported failure"
    assert where.exists(), "the folder was not made"
    assert hall.load(where)[0].name == "Someone Ashwake"


def test_the_hosted_game_records_the_dead_unless_told_not_to(tmp_path):
    """It shipped switched off, so the hall stayed empty however much died.

    That was the right default for a host that wipes its disk on every
    deploy and the wrong one everywhere else: a scoreboard nobody turned on
    is a scoreboard nobody sees.
    """
    import importlib
    import os

    import pytest

    pytest.importorskip("fastapi")

    was = os.environ.get("CRAWLER_HALL_PATH")
    os.environ["CRAWLER_HALL_PATH"] = str(tmp_path / "hall.json")
    try:
        import web.app

        importlib.reload(web.app)
        assert web.app.KEEP_HALL is True, "the dead are not being recorded"

        os.environ["CRAWLER_HALL"] = "0"
        importlib.reload(web.app)
        assert web.app.KEEP_HALL is False, "it cannot be switched off"
    finally:
        os.environ.pop("CRAWLER_HALL", None)
        if was is None:
            os.environ.pop("CRAWLER_HALL_PATH", None)
        else:
            os.environ["CRAWLER_HALL_PATH"] = was
        import web.app

        importlib.reload(web.app)


def test_the_hall_goes_on_a_mounted_volume_when_there_is_one(tmp_path):
    """A volume is the one place on a hosted box that outlives a deploy.

    It is conventionally mounted at /data, so finding one there and using it
    saves wiring up an environment variable to say the obvious thing.
    """
    import pytest

    pytest.importorskip("fastapi")
    from web.app import default_hall_path

    mounted = tmp_path / "data"
    mounted.mkdir()

    assert default_hall_path(mounted) == mounted / "hall_of_fame.json"


def test_without_a_volume_the_hall_sits_beside_the_game(tmp_path):
    """Which is what a laptop wants, and what a host without one gets."""
    import pytest

    pytest.importorskip("fastapi")
    from web.app import default_hall_path

    chosen = default_hall_path(tmp_path / "nothing-mounted-here")

    assert chosen.parent.name == "data"
    assert chosen.parent.parent.name == "AsciiCrawler"


def test_an_explicit_path_still_wins():
    import importlib
    import os

    import pytest

    pytest.importorskip("fastapi")

    was = os.environ.get("CRAWLER_HALL_PATH")
    os.environ["CRAWLER_HALL_PATH"] = "/somewhere/else/hall.json"
    try:
        import web.app

        importlib.reload(web.app)
        assert web.app.HALL_PATH.name == "hall.json"
        assert "else" in str(web.app.HALL_PATH)
    finally:
        if was is None:
            os.environ.pop("CRAWLER_HALL_PATH", None)
        else:
            os.environ["CRAWLER_HALL_PATH"] = was
        import web.app

        importlib.reload(web.app)
