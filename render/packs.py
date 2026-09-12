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

Two things sit on top of that. A key may carry a biome - `#@frozen` - and the
plain glyph answers for every biome that has no entry of its own, which is how
rock can look like ice in one place and brickwork in another while staying one
glyph to everything upstream. And pictures may live in one file rather than
fifty-one: nothing in this game is animated, so a sheet is a grid of cells and
an index says which. Both are options; a folder of loose PNGs keyed by bare
glyphs is still a pack, and is still the simplest one to write.

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

    `rect` is where to find it when the file holds more than one picture. None
    means the file is the picture, which is what a pack of loose PNGs has.
    `biome` narrows a sprite to one kind of place: a pack can draw the walls
    of the frozen deep differently from the walls of an ossuary, and anything
    it does not give a variant for falls back to the plain glyph.
    """

    glyph: str
    path: Path
    mode: str = DEFAULT_MODE
    rect: tuple | None = None
    biome: str = ""

    @property
    def key(self) -> str:
        return f"{self.glyph}@{self.biome}" if self.biome else self.glyph


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

    def sprite_for(self, glyph: str, biome: str = ""):
        """The picture for this glyph here, or None to draw the letter instead.

        A biome-specific variant wins when the pack has one; otherwise the
        plain glyph answers for everywhere. That fallback is the whole reason
        a pack can ship one wall and still be a pack - varying by biome is an
        option, not an obligation.
        """
        if biome:
            found = self.sprites.get(f"{glyph}@{biome}")
            if found is not None:
                return found
        return self.sprites.get(glyph)

    def __len__(self) -> int:
        return len(self.sprites)

    @property
    def covers(self) -> str:
        """Every glyph this pack draws, in a readable order.

        Glyphs, not keys: a pack with fifteen biome walls covers `#` once.
        """
        return "".join(sorted({split_key(key)[0] for key in self.sprites}))

    @property
    def variants(self) -> dict:
        """glyph -> the biomes it has special art for. Empty for a plain pack."""
        found: dict = {}
        for key in self.sprites:
            glyph, biome = split_key(key)
            if biome:
                found.setdefault(glyph, []).append(biome)
        return {glyph: sorted(biomes) for glyph, biomes in found.items()}


def split_key(key: str) -> tuple:
    """`"#@frozen"` -> `("#", "frozen")`; `"#"` -> `("#", "")`.

    The split starts at the second character, so the creature's own glyph -
    `@` - is a glyph and not an empty one standing in a nameless biome.
    """
    if "@" in key[1:]:
        cut = key.index("@", 1)
        return key[:cut], key[cut + 1 :]
    return key, ""


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
    if isinstance(entries, dict):
        for glyph, entry in entries.items():
            sprite = _sprite(glyph, entry, folder, default_mode, pack)
            if sprite is not None:
                pack.sprites[sprite.key] = sprite

    for sprite in _from_sheet(raw.get("atlas"), folder, default_mode, pack, "atlas"):
        pack.sprites[sprite.key] = sprite
    for sprite in _from_sheet(raw.get("walls"), folder, default_mode, pack, "walls"):
        pack.sprites[sprite.key] = sprite

    if not pack.sprites and not pack.problems:
        pack.problems.append("nothing in `sprites`, `atlas` or `walls`")
    return pack


def _from_sheet(entry, folder: Path, default_mode: str, pack: Pack, kind: str) -> list:
    """Read one packed sheet: a grid of cells, addressed by index.

    Two sheets rather than one because walls are the thing a pack is most
    likely to want fifteen of - one per biome - and mixing them in with the
    creatures would make both harder to edit. An atlas cell is found by
    counting across and down, so adding a row never moves anything already in
    the sheet.
    """
    if entry is None:
        return []
    if not isinstance(entry, dict):
        pack.problems.append(f"`{kind}` should be an object")
        return []

    name = entry.get("file")
    if not isinstance(name, str):
        pack.problems.append(f"`{kind}` has no `file`")
        return []
    path = folder / name
    if not path.is_file():
        pack.problems.append(f"`{kind}` points at {name}, which is not there")
        return []

    cell = _count(entry.get("cell_size") or pack.cell_size, f"`{kind}` cell_size", pack)
    columns = _count(entry.get("columns"), f"`{kind}` columns", pack)
    if not cell or not columns:
        return []

    mode = _mode(entry.get("mode"), pack, where=f"`{kind}`")
    places = entry.get("sprites")
    if not isinstance(places, dict) or not places:
        pack.problems.append(f"`{kind}` names a file but no sprites in it")
        return []

    found = []
    for glyph, index in places.items():
        if not isinstance(glyph, str):
            pack.problems.append(f"{glyph!r} in `{kind}` is not a glyph")
            continue
        glyph, biome = split_key(glyph)
        if len(glyph) != 1:
            pack.problems.append(f"{glyph!r} in `{kind}` is not a single glyph")
            continue
        try:
            at = int(index)
        except (TypeError, ValueError):
            pack.problems.append(f"{glyph!r} in `{kind}` has index {index!r}")
            continue
        if at < 0:
            pack.problems.append(f"{glyph!r} in `{kind}` has index {at}")
            continue
        rect = ((at % columns) * cell, (at // columns) * cell, cell, cell)
        found.append(Sprite(glyph=glyph, path=path, mode=mode, rect=rect, biome=biome))
    return found


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


def _count(value, where: str, pack: Pack) -> int:
    """A positive whole number, or 0 with a complaint filed."""
    if value is None:
        pack.problems.append(f"{where} is missing")
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        pack.problems.append(f"{where} is {value!r}, not a number")
        return 0
    if number <= 0:
        pack.problems.append(f"{where} is {number}, which should be positive")
        return 0
    return number


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
    extra = sum(len(biomes) for biomes in pack.variants.values())
    tail = f", {extra} biome variants" if extra else ""
    return f"{pack.name}: {len(pack.covers)} glyphs{tail} ({pack.covers})"
