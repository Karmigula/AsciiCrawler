"""Texture packs: reading them, checking them, and looking things up in them.

A pack maps glyphs to pictures. Glyphs, because that is the whole of what the
renderer knows about a cell by the time it comes to draw one - everything else
(what kind of thing it is, how long ago the creature saw it, what biome it is
standing in) has already been folded into a colour. Substituting on the glyph
is therefore a change to one function and nothing else, and the simulation,
the frame builder and the web server never learn that packs exist.

It follows that the keys a pack may use are exactly the glyphs on the cheat
sheet, which is a pleasant accident: pressing `j` in the game tells you what
you can retexture.

Nothing here imports pygame. This module reads a manifest and answers
questions about it; turning a path into a surface is `render/sprites.py`, and
keeping the two apart is what lets the rules be tested without a display.

A pack that is wrong should never stop the game. Every failure here - missing
manifest, unparseable JSON, a sprite naming a file that is not there - reports
itself and leaves that glyph as ASCII. Partial is the normal case, not an
error case: a pack that only draws walls is a legitimate pack.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST = "pack.json"
MODES = ("tinted", "full")
DEFAULT_MODE = "tinted"


@dataclass(frozen=True)
class Sprite:
    """One picture, and how it wants to be drawn.

    `tinted` art is greyscale and gets multiplied by the cell colour, so fog,
    biome tint and threat colouring keep working without the pack doing
    anything. `full` art is drawn as it is and only darkened for ground the
    creature is remembering rather than looking at.
    """

    glyph: str
    path: Path
    mode: str = DEFAULT_MODE


@dataclass
class Pack:
    """A folder of pictures, keyed by glyph.

    `problems` is the reason this class does not raise: a pack with a typo in
    it should draw everything it got right and say what it got wrong, and the
    caller decides whether anybody is listening.
    """

    name: str
    folder: Path
    cell_size: int = 0  # 0 means "whatever the game is using"
    sprites: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)

    def sprite_for(self, glyph: str):
        """The picture for this glyph, or None to draw the letter instead."""
        return self.sprites.get(glyph)

    def __len__(self) -> int:
        return len(self.sprites)

    @property
    def covers(self) -> str:
        """Every glyph this pack draws, in a readable order."""
        return "".join(sorted(self.sprites))


EMPTY = Pack(name="ascii", folder=Path("."))


def load(folder) -> Pack:
    """Read a pack from a folder. Never raises; look at `problems`."""
    folder = Path(folder)
    pack = Pack(name=folder.name, folder=folder)

    manifest = folder / MANIFEST
    if not manifest.is_file():
        pack.problems.append(f"no {MANIFEST} in {folder}")
        return pack
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as reason:
        pack.problems.append(f"{manifest} could not be read: {reason}")
        return pack
    if not isinstance(raw, dict):
        pack.problems.append(f"{manifest} should hold an object")
        return pack

    pack.name = str(raw.get("name") or folder.name)
    pack.cell_size = _size(raw.get("cell_size"), pack)
    default_mode = _mode(raw.get("mode"), pack, where="the pack")

    entries = raw.get("sprites")
    if not isinstance(entries, dict):
        pack.problems.append("`sprites` should be an object of glyph -> file")
        return pack

    for glyph, entry in entries.items():
        sprite = _sprite(glyph, entry, folder, default_mode, pack)
        if sprite is not None:
            pack.sprites[sprite.glyph] = sprite
    return pack


def _size(value, pack: Pack) -> int:
    if value is None:
        return 0
    try:
        size = int(value)
    except (TypeError, ValueError):
        pack.problems.append(f"cell_size {value!r} is not a number")
        return 0
    if size <= 0:
        pack.problems.append(f"cell_size {size} should be positive")
        return 0
    return size


def _mode(value, pack: Pack, where: str) -> str:
    if value is None:
        return DEFAULT_MODE
    if value not in MODES:
        pack.problems.append(
            f"{where} asks for mode {value!r}; expected one of {', '.join(MODES)}"
        )
        return DEFAULT_MODE
    return value


def _sprite(glyph, entry, folder: Path, default_mode: str, pack: Pack):
    """One entry of the manifest, or None if it is not usable."""
    if not isinstance(glyph, str) or len(glyph) != 1:
        pack.problems.append(f"{glyph!r} is not a single glyph")
        return None

    mode = default_mode
    if isinstance(entry, str):
        name = entry
    elif isinstance(entry, dict):
        name = entry.get("file")
        mode = _mode(entry.get("mode"), pack, where=f"{glyph!r}")
        if not isinstance(name, str):
            pack.problems.append(f"{glyph!r} has no `file`")
            return None
    else:
        pack.problems.append(f"{glyph!r} should name a file")
        return None

    path = folder / name
    # Checked here rather than at draw time so a pack reports everything wrong
    # with it at once, instead of a surprise the first time the creature walks
    # past the one tile that uses it.
    if not path.is_file():
        pack.problems.append(f"{glyph!r} points at {name}, which is not there")
        return None
    return Sprite(glyph=glyph, path=path, mode=mode)


def discover(root) -> list:
    """Every pack folder under `root`, by name. Missing root means none."""
    root = Path(root)
    if not root.is_dir():
        return []
    return sorted(
        (folder for folder in root.iterdir() if (folder / MANIFEST).is_file()),
        key=lambda folder: folder.name.lower(),
    )


def describe(pack: Pack) -> str:
    """One line about a pack, for a menu or a console."""
    if not pack.sprites:
        return f"{pack.name}: nothing usable"
    return f"{pack.name}: {len(pack.sprites)} sprites ({pack.covers})"
