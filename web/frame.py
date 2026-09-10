"""Turn a drawable frame into something a browser can eat.

The desktop renderer hands pygame a grid of (glyph, colour) and a matching
grid of background washes. A socket cannot carry that shape cheaply, so this
flattens it: glyphs become one string per row, colours become indices into a
per-frame palette, and runs of identical colour collapse to (index, count).

The compression is not decoration. A 96x44 window is 4,224 cells, and at ten
frames a second a naive `[[r, g, b], ...]` per cell is megabytes a minute for
every viewer. Fog shading means neighbouring cells usually share a colour
exactly, so run-length coding does most of the work for free.
"""

from config import Config
from render.frame import build_frame

Color = tuple[int, int, int]

BLANK = " "  # a cell nothing is known about


def _hex(color: Color) -> str:
    return "#%02x%02x%02x" % (color[0], color[1], color[2])


class _Palette:
    """Distinct colours in this frame, in first-seen order."""

    def __init__(self) -> None:
        self._index: dict[Color, int] = {}
        self.entries: list[str] = []

    def index_of(self, color: Color | None) -> int:
        """-1 means 'nothing here', which the client skips painting."""
        if color is None:
            return -1
        key = (color[0], color[1], color[2])
        found = self._index.get(key)
        if found is None:
            found = len(self.entries)
            self._index[key] = found
            self.entries.append(_hex(key))
        return found


def _runs(indices: list[int]) -> list[int]:
    """Flatten a row to [index, count, index, count, ...]."""
    out: list[int] = []
    for value in indices:
        if out and out[-2] == value:
            out[-1] += 1
        else:
            out.extend((value, 1))
    return out


def serialize(
    world,
    agent,
    config: Config,
    cols: int,
    rows: int,
    *,
    hud: list | None = None,
    worn: list | None = None,
    log: list | None = None,
    viewers: int = 0,
) -> dict:
    """One frame of the aquarium, ready for `json.dumps`.

    The window is centred on the agent, which is the only camera this thing
    has ever needed: nobody is steering it, so there is nowhere else to look.
    """
    origin = (agent.x - cols // 2, agent.y - rows // 2)
    cells, backgrounds, _ = build_frame(world, agent, config, origin, cols, rows)

    palette = _Palette()
    glyph_rows: list[str] = []
    fg_rows: list[list[int]] = []
    bg_rows: list[list[int]] = []
    for y in range(rows):
        line: list[str] = []
        fg: list[int] = []
        for x in range(cols):
            cell = cells[y][x]
            if cell is None:
                line.append(BLANK)
                fg.append(-1)
            else:
                glyph, color = cell
                line.append(glyph)
                fg.append(palette.index_of(color))
        glyph_rows.append("".join(line))
        fg_rows.append(_runs(fg))
        bg_rows.append(_runs([palette.index_of(c) for c in backgrounds[y]]))

    here = world.biome_at(agent.x, agent.y)
    return {
        "tick": agent.tick_count,
        "cols": cols,
        "rows": rows,
        "glyphs": glyph_rows,
        "fg": fg_rows,
        "bg": bg_rows,
        "palette": palette.entries,
        "agent": [cols // 2, rows // 2, _hex(config.agent_color)],
        "biome": here.label,
        "hud": [[text, _hex(color)] for text, color in (hud or [])],
        "worn": [[text, _hex(color)] for text, color in (worn or [])],
        "log": [[text, _hex(color)] for text, color in (log or [])],
        "viewers": viewers,
    }
