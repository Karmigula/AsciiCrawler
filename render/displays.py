"""Where the monitors actually are, asked of the operating system.

pygame reports display *sizes* but not their positions, and every way of
guessing the positions from the sizes is wrong for a real desk. Monitors to
the left of the primary one sit at negative x - a three-monitor setup can
easily run from -3520 to +2560 - so laying them out left to right from zero in
index order puts two thirds of the desktop somewhere it is not.

Windows will simply say. `EnumDisplayMonitors` returns each monitor's rectangle
in the same virtual-desktop coordinates that SDL uses for window positions, so
the two can be mixed freely. No dependency: it is a ctypes call.

On anything else, or if the call fails, this returns an empty list and the
caller falls back to asking pygame and guessing.
"""

import sys

Rect = tuple[int, int, int, int]


def monitor_rects() -> list[Rect]:
    """(x, y, width, height) for every monitor, in enumeration order.

    Order matches `pygame.display.get_desktop_sizes()` on the machines this
    was checked against, but nothing here depends on that: placement uses the
    rectangles directly rather than a display index.
    """
    if not sys.platform.startswith("win"):
        return []
    try:
        return _windows_monitor_rects()
    except Exception:  # noqa: BLE001 - any ctypes/OS failure means "fall back"
        return []


def _windows_monitor_rects() -> list[Rect]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )
    primary_flag = 1  # MONITORINFOF_PRIMARY
    found: list[tuple[Rect, bool]] = []

    def collect(handle, _hdc, _rect, _param):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            area = info.rcMonitor
            found.append(
                (
                    (
                        area.left,
                        area.top,
                        area.right - area.left,
                        area.bottom - area.top,
                    ),
                    bool(info.dwFlags & primary_flag),
                )
            )
        return True

    if not user32.EnumDisplayMonitors(None, None, callback_type(collect), 0):
        return []
    return [rect for rect, _ in found]


def primary_index(rects: list[Rect]) -> int:
    """Which rectangle is the primary display: the one whose origin is (0, 0).

    Windows defines the primary monitor as the origin of the virtual desktop,
    which is what makes every other monitor's coordinates negative or positive
    relative to it.
    """
    for index, (x, y, _, _) in enumerate(rects):
        if x == 0 and y == 0:
            return index
    return 0
