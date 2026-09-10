"""The title screen: what it says and how the highlight moves."""

from config import DEFAULT_CONFIG
from render.menu import (
    ENTRIES,
    TITLE_ROWS,
    block_text,
    menu_lines,
    move_selection,
    title_lines,
)


def _text(lines) -> str:
    return "\n".join(text for text, _ in lines)


def test_the_title_is_five_rows_of_block_letters():
    rows = block_text("ASCII")
    assert len(rows) == 5
    assert all(set(row) <= {"#", " "} for row in rows), "ASCII only, no box drawing"
    assert all(len(row) == len(rows[0]) for row in rows), "rows line up"


def test_an_unknown_character_becomes_a_gap_rather_than_breaking():
    rows = block_text("A?")
    assert len(rows) == 5
    assert all(len(row) == len(rows[0]) for row in rows)


def test_the_title_block_is_the_size_the_renderer_is_told():
    """The renderer gives exactly these lines the larger font."""
    assert len(title_lines(DEFAULT_CONFIG)) == TITLE_ROWS


def test_the_menu_names_every_entry():
    body = _text(menu_lines(0, 4242, DEFAULT_CONFIG))
    for label, blurb in ENTRIES:
        assert label in body
        assert blurb in body


def test_the_menu_shows_the_seed_and_the_keys():
    body = _text(menu_lines(0, 1234, DEFAULT_CONFIG))
    assert "1234" in body
    assert "enter" in body and "esc" in body


def test_only_the_selected_entry_is_marked():
    for index in range(len(ENTRIES)):
        marked = [
            text for text, _ in menu_lines(index, 1, DEFAULT_CONFIG) if text.startswith(">")
        ]
        assert len(marked) == 1
        assert ENTRIES[index][0] in marked[0] or "resume" in marked[0]


def test_the_selected_entry_is_coloured_differently():
    lines = menu_lines(0, 1, DEFAULT_CONFIG)
    picked = [colour for text, colour in lines if text.startswith(">")]
    assert picked == [DEFAULT_CONFIG.menu_pick_color]


def test_a_running_creature_is_resumed_not_started():
    """The menu should not offer to start something already happening."""
    fresh = _text(menu_lines(0, 1, DEFAULT_CONFIG, running=False))
    ongoing = _text(menu_lines(0, 1, DEFAULT_CONFIG, running=True))
    assert "watch" in fresh and "resume" not in fresh
    assert "resume" in ongoing


def test_the_highlight_wraps_around():
    last = len(ENTRIES) - 1
    assert move_selection(0, -1) == last
    assert move_selection(last, 1) == 0
    assert move_selection(0, 1) == 1


def test_entries_line_up_in_one_column():
    """Centred lines of differing length read as ragged; equal ones read as a
    list, which is why label and blurb share a padded line."""
    lines = [text for text, _ in menu_lines(0, 1, DEFAULT_CONFIG)]
    # Matched on the blurbs, which are unique - "watch" also appears in the
    # tagline, and a filter that catches that proves nothing about alignment.
    entry_lines = [t for t in lines if any(blurb in t for _, blurb in ENTRIES)]
    assert len(entry_lines) == len(ENTRIES)
    # The marker sits in column 0 of the selected line, so "first non-space"
    # is meant to differ. What has to line up is the blurb column.
    blurb_columns = {
        line.index(blurb)
        for line in entry_lines
        for _, blurb in ENTRIES
        if blurb in line
    }
    assert len(blurb_columns) == 1, "every blurb starts in the same column"
