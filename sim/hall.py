"""The hall of fame: every life the creature has lived, and how it ended.

Each death already makes a complete little story - how deep it got, what it was
wearing, what finally killed it - and until now all of that vanished the moment
the agent respawned. This keeps the best of them.

Ranked by a score rather than by any single number, because a level 9 that
never left the first ring is a lesser run than a level 6 that reached the deep
caverns, and neither is obviously better than one with four hundred kills. The
weights are a judgement, not a fact, and they live in one place so they can be
argued with.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from paths import beside

# Next to the game, so the dead survive the executable being replaced by the
# next release. The hosted build passes its own path; see `web/app.py`.
DEFAULT_PATH = beside("hall_of_fame.json")
LIMIT = 20


@dataclass(frozen=True)
class Fallen:
    """One life, from spawn to death."""

    seed: int
    level: int
    kills: int
    depth: int  # furthest it ever got from the world origin
    ticks: int  # how long the life lasted
    killer: str
    archetype: str
    gold: int = 0
    # Defaulted so a hall written before names existed still loads: `load`
    # drops any record whose fields do not match, and a missing name is not
    # worth losing somebody's best run over.
    name: str = ""

    def epitaph(self) -> str:
        """One line, the way a tombstone would put it."""
        life = f"level {self.level}, {self.kills} kills, {self.depth} deep - {self.killer}"
        return f"{self.name}: {life}" if self.name else life


def score(entry: Fallen) -> int:
    """How good a run was. Depth counts most; a level that never left home is
    worth less than a modest one that got somewhere."""
    return entry.level * 60 + entry.kills * 4 + entry.depth


def load(path: Path | None = None) -> list[Fallen]:
    """The stored hall, best first. Anything unreadable is an empty hall."""
    target = DEFAULT_PATH if path is None else path
    try:
        with open(target, encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(Fallen(**item))
        except TypeError:
            # A record from an older version with different fields. Skipping it
            # loses one life; refusing to read the file would lose all of them.
            continue
    return ranked(entries)


def save(entries: list[Fallen], path: Path | None = None) -> bool:
    """Write the hall out. Failing to record a death is not worth a crash.

    Makes the folder if it is not there. A mounted volume starts empty, so
    without this the first death on a fresh host wrote nothing, reported
    nothing, and left a hall that stayed empty forever - the failure is
    swallowed here on purpose, which is exactly what would have hidden it.
    """
    target = DEFAULT_PATH if path is None else path
    try:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump([asdict(entry) for entry in entries], handle, indent=2)
        return True
    except OSError:
        return False


def ranked(entries: list[Fallen], limit: int = LIMIT) -> list[Fallen]:
    """Best first, capped. Ties break toward the deeper run."""
    return sorted(entries, key=lambda e: (-score(e), -e.depth, -e.level))[:limit]


def remember(entry: Fallen, path: Path | None = None, limit: int = LIMIT) -> list[Fallen]:
    """Add one life to the hall and write it back, returning the new hall."""
    entries = ranked([*load(path), entry], limit)
    save(entries, path)
    return entries
