"""Remembering the settings between runs.

Small on purpose: a flat JSON file of key to value, next to the code, holding
only what the settings screen offers. It is read by the game and by the soak
runner, which is the point - a worker count you set in the menu should be the
one a soak uses, and before this file existed the menu wrote it into an
in-session config that nothing ever read.

Every failure here is survivable and silent by design. A missing file is the
first run; a corrupt one is not worth stopping a toy for. Both give defaults.
"""

import json
from pathlib import Path

from paths import beside

# Beside the game rather than inside it: a frozen build unpacks itself to a
# temporary folder that is deleted on exit, so settings written there would
# last exactly one session.
DEFAULT_PATH = beside("settings.json")


def load_values(path: Path | None = None) -> dict:
    """The stored settings, or an empty dict if there are none to be had."""
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return {}
    return stored if isinstance(stored, dict) else {}


def save_values(values: dict, path: Path | None = None) -> bool:
    """Write the settings out. Returns whether it worked.

    The caller is not expected to care: failing to save a preference should
    not interrupt anything, and the return value is there for tests.
    """
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(values, handle, indent=2, sort_keys=True)
        return True
    except OSError:
        return False
