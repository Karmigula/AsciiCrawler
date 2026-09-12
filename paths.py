"""Where things are, given the game might be a folder of files or one .exe.

Running from source, everything lives together in the repository and none of
this matters. Frozen into a single executable it splits in two, and the split
is the whole reason this module exists:

- **Bundled** things are shipped inside the executable and unpacked to a
  temporary folder that is deleted on exit. The font is one of these. Writing
  there is pointless - the file is gone the moment the game closes.
- **Beside** things live next to the executable, where somebody can see them
  in a file manager: the texture packs they may want to add to, the settings
  they changed, the hall of fame they earned. These have to survive the exe
  being replaced by the next release, so they are never inside it.

`sys.frozen` and `sys._MEIPASS` are PyInstaller's, and both are absent when
running from source, which is what makes the fallbacks below the normal case
rather than an error case.
"""

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
_SOURCE = Path(__file__).resolve().parent


def bundled(*parts) -> Path:
    """A read-only file shipped with the game: fonts, and nothing else yet."""
    root = Path(getattr(sys, "_MEIPASS", _SOURCE)) if FROZEN else _SOURCE
    return root.joinpath(*parts)


def beside(*parts) -> Path:
    """A file the player owns, next to the executable rather than inside it.

    From source this is the repository, which is where `settings.json`,
    `hall_of_fame.json` and `packs/` already were - so nothing moves for
    anybody who runs `python main.py`.
    """
    root = Path(sys.executable).resolve().parent if FROZEN else _SOURCE
    return root.joinpath(*parts)


def note(message: str) -> None:
    """Print, when there may be nowhere to print to.

    A windowed build has no console and PyInstaller sets `sys.stdout` to None,
    so an ordinary `print` of something as minor as a typo in a pack manifest
    would take the whole game down with an AttributeError. Diagnostics are
    never worth that.
    """
    if sys.stdout is None:
        return
    try:
        print(message)
    except (OSError, ValueError):  # a closed or detached stream
        pass
