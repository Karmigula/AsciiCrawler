"""A short rolling log of what just happened to the agent.

The aquarium is watchable without this, but only just: a glyph moving on a
grid does not tell you that it fled a troll, found a cruel sword, or died for
the fourth time. The chronicle is the difference between watching a dot and
watching a story.

Bounded on purpose. It is a window on the recent past, not a history of the
run - an unbounded log in a process meant to run for days is a leak with good
intentions.
"""

from collections import deque


class Chronicle:
    """The last `limit` things worth mentioning, oldest first."""

    def __init__(self, limit: int = 8) -> None:
        self._entries: deque = deque(maxlen=limit)
        self.total = 0

    def record(self, tick: int, text: str) -> None:
        self._entries.append((tick, text))
        self.total += 1

    def recent(self, count: int | None = None) -> list:
        """The most recent entries, oldest first."""
        entries = list(self._entries)
        return entries if count is None else entries[-count:]

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)


def an(noun: str) -> str:
    """"a troll", but "an orc" - the article the noun actually takes.

    Death causes are written once and then read everywhere: the recent log,
    the tombstone, the hall of fame column. "a orc" in all three is a small
    thing that makes the whole page look machine-written.
    """
    article = "an" if noun[:1].lower() in "aeiou" else "a"
    return f"{article} {noun}"


def killed(monster) -> str:
    return f"killed the {monster.kind.key}"


def slain_by(monster) -> str:
    return f"slain by a {monster.kind.key}"


def died() -> str:
    return "died in the dark"


def found(item) -> str:
    if item.kind.slot is None:
        return f"picked up {item.kind.key}"
    if item.affixes:
        return f"found a {item.name}"
    return f"found a plain {item.kind.key}"


def equipped(item) -> str:
    return f"put on the {item.name}"


def levelled(level: int) -> str:
    return f"reached level {level}"


def boss_stirs(name: str) -> str:
    return f"{name} stirs"


def boss_hunts(name: str) -> str:
    return f"{name} is hunting"


def cast(spell: str, target: str) -> str:
    return f"{spell} at the {target}"


def touched_shrine(kind: str, effect: str, blessed: bool) -> str:
    """What the totem did, named plainly enough to follow without a legend."""
    return f"{'blessed with' if blessed else 'cursed with'} {effect} at {kind}"


def effect_ended(label: str) -> str:
    return f"{label} faded"


def sprang_trap(damage: int) -> str:
    return f"stepped in a trap ({damage} damage)"


def spotted_trap() -> str:
    return "spotted a trap"


def fled(kind_key: str) -> str:
    return f"fled from the {kind_key}"


def robbed_grave() -> str:
    return "recovered gear from its own grave"
