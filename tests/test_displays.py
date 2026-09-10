"""Asking the operating system where the monitors are."""

import sys

import pytest

from render.displays import monitor_rects, primary_index


def test_every_rect_is_four_whole_numbers():
    for rect in monitor_rects():
        assert len(rect) == 4
        assert all(isinstance(value, int) for value in rect)


def test_reported_monitors_have_real_extent():
    for _, _, width, height in monitor_rects():
        assert width > 0 and height > 0


def test_monitors_do_not_overlap():
    """Overlapping rectangles would make "which display is this on" ambiguous."""
    rects = monitor_rects()
    for i, (ax, ay, aw, ah) in enumerate(rects):
        for bx, by, bw, bh in rects[i + 1 :]:
            apart = ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
            assert apart, "monitors should tile the desktop, not overlap"


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows only")
def test_windows_reports_at_least_one_monitor():
    assert monitor_rects(), "the OS should name at least the primary display"


def test_the_primary_display_is_the_origin_of_the_desktop():
    """Windows puts the primary monitor at (0, 0); everything else is relative
    to it, which is why monitors to its left have negative coordinates."""
    rects = monitor_rects()
    if rects:
        assert rects[primary_index(rects)][:2] == (0, 0) or primary_index(rects) == 0


def test_primary_index_finds_the_origin_in_a_synthetic_layout():
    left_of_primary = [(-1920, 0, 1920, 1080), (0, 0, 2560, 1080)]
    assert primary_index(left_of_primary) == 1


def test_primary_index_falls_back_to_the_first_rect():
    assert primary_index([(-100, -100, 800, 600)]) == 0
    assert primary_index([]) == 0


def test_negative_origins_survive_the_round_trip():
    """The bug this module exists for: a monitor left of the primary sits at
    negative x, and no arrangement of display *sizes* can tell you that."""
    from render.screen import display_for_point

    rects = [(0, 0, 2560, 1080), (-1920, 0, 1920, 1080)]
    assert display_for_point(rects, -1000, 500) == 1
    assert display_for_point(rects, 1000, 500) == 0
