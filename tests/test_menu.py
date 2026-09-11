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


def test_every_screen_title_renders_with_all_its_letters():
    """Titles were drawn from an alphabet that only covered the word CRAWLER.

    Unknown letters fall back to blanks, so SETTINGS shipped as "SE  I  S",
    SOAK as "S A " and HALL as " ALL" - three screens with holes punched in
    their headings and nothing anywhere to say so.
    """
    from render.menu import _LETTERS

    for title in ("CRAWLER", "SETTINGS", "SOAK", "HALL"):
        for letter in title:
            assert letter in _LETTERS, f"{title} has no block letter for {letter!r}"
        rows = block_text(title)
        for row in rows:
            assert row.strip(), "a title row came out empty"
        # Every letter contributes ink, so no five-column slice is all blank.
        for index in range(len(title)):
            at = index * 6
            slice_ = [row[at : at + 5] for row in rows]
            assert any(cell.strip() for cell in slice_), (
                f"{title!r} renders a gap where {title[index]!r} should be"
            )


def test_the_alphabet_covers_letters_and_digits():
    """So the next title someone writes does not come out with holes in it."""
    from string import ascii_uppercase, digits

    from render.menu import _LETTERS

    for letter in ascii_uppercase + digits:
        assert letter in _LETTERS, f"no block letter for {letter!r}"
        assert len(_LETTERS[letter]) == 5, letter
        assert all(len(row) == 5 for row in _LETTERS[letter]), letter


def test_the_desktop_hall_shows_only_as_many_runs_as_the_window_fits():
    """`draw_centered` does not clip: anything past the bottom is just gone.

    The hall keeps twenty now, which fits a default window and does not fit a
    short one, so the screen asks for a number rather than handing over the
    whole list and hoping.
    """
    from config import DEFAULT_CONFIG
    from render.menu import hall_lines
    from sim.hall import Fallen

    runs = [
        Fallen(
            seed=n, level=5, kills=9, depth=100, ticks=800,
            killer="a rat", archetype="scout", name=f"Someone {n}",
        )
        for n in range(20)
    ]

    full = hall_lines(runs, DEFAULT_CONFIG, limit=20)
    cramped = hall_lines(runs, DEFAULT_CONFIG, limit=5)

    assert len(cramped) < len(full)
    assert sum("Someone" in text for text, _ in cramped) == 5
    assert sum("Someone" in text for text, _ in full) == 20


def test_the_desktop_hall_shows_only_as_many_runs_as_the_window_fits():
    """`draw_centered` does not clip: anything past the bottom is just gone.

    The hall keeps twenty now, which suits a default window and does not suit
    a short one, so the screen asks how many will fit rather than handing over
    the whole list and hoping.
    """
    from config import DEFAULT_CONFIG
    from render.menu import hall_lines
    from sim.hall import Fallen

    runs = [
        Fallen(
            seed=n, level=5, kills=9, depth=100, ticks=800,
            killer="a rat", archetype="scout", name=f"Someone {n}",
        )
        for n in range(20)
    ]

    full = hall_lines(runs, DEFAULT_CONFIG, limit=20)
    cramped = hall_lines(runs, DEFAULT_CONFIG, limit=5)

    assert len(cramped) < len(full)
    assert sum("Someone" in text for text, _ in cramped) == 5
    assert sum("Someone" in text for text, _ in full) == 20
