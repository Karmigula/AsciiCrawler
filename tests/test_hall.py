"""The hall of fame: recording lives, ranking them, surviving a bad file."""

import json

import pytest

from config import DEFAULT_CONFIG
from render.menu import hall_lines
from sim.hall import Fallen, load, ranked, remember, save, score


def life(level=1, kills=0, depth=0, ticks=100, killer="a rat", seed=1):
    return Fallen(
        seed=seed,
        level=level,
        kills=kills,
        depth=depth,
        ticks=ticks,
        killer=killer,
        archetype="scout",
    )


@pytest.fixture
def hall_file(tmp_path):
    return tmp_path / "hall.json"


def test_a_life_survives_being_written_and_read(hall_file):
    entry = life(level=4, kills=30, depth=500, killer="a troll")
    remember(entry, hall_file)
    assert load(hall_file) == [entry]


def test_the_best_run_comes_first(hall_file):
    shallow = life(level=9, depth=20, kills=5)
    deep = life(level=6, depth=900, kills=200)
    remember(shallow, hall_file)
    remember(deep, hall_file)
    assert load(hall_file)[0] == deep, "getting somewhere beats levelling at home"


def test_depth_counts_for_more_than_a_level():
    assert score(life(level=1, depth=600)) > score(life(level=6, depth=0))


def test_the_hall_is_capped(hall_file):
    for i in range(30):
        remember(life(level=i, depth=i * 10), hall_file)
    stored = load(hall_file)
    assert len(stored) == 12
    assert stored[0].level == 29, "and it keeps the best, not the newest"


def test_a_missing_hall_is_an_empty_one(tmp_path):
    assert load(tmp_path / "nothing.json") == []


def test_a_corrupt_hall_does_not_take_the_game_with_it(hall_file):
    hall_file.write_text("{not json at all", encoding="utf-8")
    assert load(hall_file) == []
    remember(life(level=3), hall_file)
    assert len(load(hall_file)) == 1, "and it can be written again afterwards"


def test_a_record_from_an_older_version_is_skipped_not_fatal(hall_file):
    """Losing one life beats refusing to read the rest of them."""
    good = life(level=5, depth=100)
    payload = [{"seed": 1, "unknown_field": True}, json.loads(json.dumps(good.__dict__))]
    hall_file.write_text(json.dumps(payload), encoding="utf-8")
    stored = load(hall_file)
    assert stored == [good]


def test_ranking_is_stable_and_prefers_the_deeper_run():
    a = life(level=3, kills=0, depth=200)
    b = life(level=3, kills=0, depth=200)
    assert ranked([a, b]) == [a, b]


def test_an_empty_hall_says_so_rather_than_showing_a_blank_table():
    body = "\n".join(text for text, _ in hall_lines([], DEFAULT_CONFIG))
    assert "nothing has died" in body


def test_the_table_lines_up_with_its_header():
    entries = [life(level=11, kills=410, depth=1614, ticks=31000, killer="a dragon")]
    lines = [text for text, _ in hall_lines(entries, DEFAULT_CONFIG)]
    header = next(t for t in lines if "level" in t and "kills" in t)
    row = next(t for t in lines if t.strip().startswith("1."))
    assert header.index("kills") + len("kills") == row.index("410") + len("410")
    assert header.index("depth") + len("depth") == row.index("1614") + len("1614")


def test_the_top_run_is_highlighted():
    entries = [life(level=9, depth=900), life(level=1, depth=1)]
    lines = hall_lines(sorted(entries, key=lambda e: -score(e)), DEFAULT_CONFIG)
    rows = [(t, c) for t, c in lines if t.strip()[:2] in ("1.", "2.")]
    assert rows[0][1] == DEFAULT_CONFIG.menu_pick_color
    assert rows[1][1] != DEFAULT_CONFIG.menu_pick_color


def test_a_long_build_name_cannot_break_the_columns():
    entry = Fallen(1, 5, 5, 5, 5, "a very long killer name indeed", "a/b/c/d/e/f/g/h/i/j/k/l")
    lines = [text for text, _ in hall_lines([entry], DEFAULT_CONFIG)]
    row = next(t for t in lines if t.strip().startswith("1."))
    header = next(t for t in lines if "build" in t)
    assert len(row) == len(header)
