"""Which monitor a window is on: the geometry, without needing two monitors.

The placement code is hard to test because it depends on a real multi-display
desktop. This is the part that does not: given display rectangles and a point,
which display is it on.
"""

from render.screen import display_for_point

# Two 1920x1080 monitors side by side, sharing a top edge.
SIDE_BY_SIDE = [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]
# One above the other - the arrangement the old left-to-right guess got wrong.
STACKED = [(0, 0, 1920, 1080), (0, -1080, 1920, 1080)]
# A smaller second monitor hung off the right, vertically offset.
OFFSET = [(0, 0, 2560, 1440), (2560, 300, 1920, 1080)]


def test_a_point_on_the_primary_display():
    assert display_for_point(SIDE_BY_SIDE, 100, 100) == 0


def test_a_point_on_the_second_display():
    assert display_for_point(SIDE_BY_SIDE, 2000, 500) == 1


def test_the_boundary_belongs_to_the_display_that_starts_there():
    assert display_for_point(SIDE_BY_SIDE, 1919, 0) == 0
    assert display_for_point(SIDE_BY_SIDE, 1920, 0) == 1


def test_a_stacked_arrangement_is_read_by_height_too():
    """Left-to-right inference put everything on display 0 here."""
    assert display_for_point(STACKED, 500, 500) == 0
    assert display_for_point(STACKED, 500, -500) == 1


def test_a_vertically_offset_display():
    assert display_for_point(OFFSET, 3000, 800) == 1
    assert display_for_point(OFFSET, 2000, 800) == 0


def test_dead_space_beside_an_offset_display_goes_to_the_closer_one():
    """(3000, 100) is on neither monitor: it sits in the gap above the second
    one. It is 440px past the right edge of the first and 200px above the
    second, so the second is the honest answer."""
    assert display_for_point(OFFSET, 3000, 100) == 1


def test_a_point_off_every_display_picks_the_nearest():
    """A window dragged half off the desktop still has to land somewhere."""
    assert display_for_point(SIDE_BY_SIDE, -400, 500) == 0
    assert display_for_point(SIDE_BY_SIDE, 5000, 500) == 1


def test_no_displays_reported_does_not_crash():
    assert display_for_point([], 10, 10) == 0


def test_a_single_display_is_always_the_answer():
    single = [(0, 0, 1280, 720)]
    for point in ((0, 0), (1279, 719), (-100, -100), (9999, 9999)):
        assert display_for_point(single, *point) == 0
