"""The title screen: block-letter art and the menu, as lines of text.

Pygame-free and pure, like the HUD, so what the screen *says* can be tested
without opening a window. The block alphabet is spelled out here rather than
pulled from a figlet font: only eight letters are needed, and a table that
small is easier to read - and to adjust to the cell grid - than a dependency.

Only ASCII is used. The bundled font has box-drawing glyphs, but a title that
silently turns into tofu on a machine without them is a poor first impression,
and `#` is the same character the walls are drawn with.
"""

from dataclasses import dataclass

Color = tuple[int, int, int]
Line = tuple[str, Color]

# Five rows per letter, five columns wide. Anything not here renders as a gap.
_LETTERS: dict[str, tuple[str, ...]] = {
    "A": (" ### ", "#   #", "#####", "#   #", "#   #"),
    "C": (" ####", "#    ", "#    ", "#    ", " ####"),
    "E": ("#####", "#    ", "###  ", "#    ", "#####"),
    "I": ("#####", "  #  ", "  #  ", "  #  ", "#####"),
    "L": ("#    ", "#    ", "#    ", "#    ", "#####"),
    "R": ("#### ", "#   #", "#### ", "#  # ", "#   #"),
    "S": (" ####", "#    ", " ### ", "    #", "#### "),
    "W": ("#   #", "#   #", "# # #", "## ##", "#   #"),
    " ": ("     ", "     ", "     ", "     ", "     "),
}

_ROWS = 5


def block_text(word: str) -> list[str]:
    """Render a word as five rows of block letters."""
    rows = []
    for row in range(_ROWS):
        rows.append(
            " ".join(_LETTERS.get(letter, _LETTERS[" "])[row] for letter in word.upper())
        )
    return rows


ENTRIES: tuple[tuple[str, str], ...] = (
    ("watch", "let it out into the dark"),
    ("new world", "roll a different dungeon"),
    ("settings", "workers, colour, flourishes"),
    ("soak", "test many worlds at once"),
    ("hall of fame", "every life, and how it ended"),
    ("quit", "close the window"),
)


# Wide enough for the longest entry, worked out rather than guessed: adding
# "hall of fame" to the list silently pushed every blurb out of line.
_LABEL_WIDTH = max(len(label) for label, _ in ENTRIES) + 1

TITLE_ROWS = _ROWS * 2 + 1
"""How many lines at the top of `menu_lines` are title art, so the renderer
can give them the larger font."""


def title_lines(config) -> list[Line]:
    """The block-letter title, as coloured lines."""
    lines: list[Line] = [(row, config.menu_title_color) for row in block_text("ASCII")]
    lines.append(("", config.menu_dim_color))
    lines.extend((row, config.menu_title_color) for row in block_text("CRAWLER"))
    return lines


def menu_lines(selected: int, seed: int, config, running: bool = False) -> list[Line]:
    """The whole title screen: art, tagline, entries, and the footer.

    `selected` is the highlighted entry; `running` swaps the first entry's
    wording when there is already a creature to go back to, so the menu does
    not offer to start something that is already happening.
    """
    lines = title_lines(config)
    lines.append(("", config.menu_dim_color))
    lines.append(("nobody plays it. you watch it.", config.menu_dim_color))
    lines.append(("", config.menu_dim_color))

    for index, (label, blurb) in enumerate(ENTRIES):
        if index == 0 and running:
            label = "resume"
        chosen = index == selected
        marker = ">" if chosen else " "
        colour = config.menu_pick_color if chosen else config.menu_text_color
        # Label and blurb share a line, padded to a fixed column. Centring
        # alternating short and long lines reads as ragged; one line per entry
        # of equal length reads as a list.
        lines.append((f"{marker} {label:<{_LABEL_WIDTH}}  {blurb}", colour))

    lines.append(("", config.menu_dim_color))
    lines.append((f"world seed {seed}", config.menu_dim_color))
    lines.append(("up/down choose    enter start    esc quit", config.menu_dim_color))
    lines.append(("F10 borderless    F11 fullscreen", config.menu_dim_color))
    return lines


def move_selection(selected: int, delta: int) -> int:
    """Wrap the highlight around the entry list."""
    return (selected + delta) % len(ENTRIES)


@dataclass
class Setting:
    """One adjustable value, and the choices it steps between."""

    key: str
    label: str
    blurb: str
    values: tuple
    index: int = 0

    @property
    def value(self):
        return self.values[self.index]

    def shown(self) -> str:
        value = self.value
        if isinstance(value, bool):
            return "on" if value else "off"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)


def default_settings(config, max_workers: int) -> list[Setting]:
    """The adjustable settings, with the current config as their starting point.

    Worker count is first because it is the one that scales with the machine.
    It is honest about what it touches: the simulation the window shows is one
    world on one core, and no number of workers changes that. Parallelism buys
    coverage when soak-testing many worlds, not a faster creature.
    """
    workers = tuple(range(1, max(2, max_workers + 1)))
    washes = (0.0, 0.15, 0.3, 0.44, 0.6, 0.8)
    speeds = tuple(config.speed_steps)
    return [
        Setting(
            "workers",
            "soak workers",
            "parallel worlds when soak-testing; not the game",
            workers,
            index=min(len(workers) - 1, max(0, max_workers - 1)),
        ),
        Setting(
            "speed",
            "start speed",
            "how fast it runs when you press watch",
            speeds,
            index=0,
        ),
        Setting(
            "on_death",
            "on death",
            "keep the world and its memories, or start over",
            ("same world", "new world"),
            index=1 if config.new_world_on_death else 0,
        ),
        Setting(
            "wash",
            "biome colour",
            "how strongly the ground is tinted",
            washes,
            index=_closest(washes, config.background_strength.get("visible", 0.44)),
        ),
        Setting(
            "moss",
            "moss",
            "cosmetic speckle on old stone",
            (True, False),
            index=0 if config.moss_chance > 0 else 1,
        ),
    ]


def _closest(values, target) -> int:
    return min(range(len(values)), key=lambda i: abs(values[i] - target))


def adjust(settings: list[Setting], selected: int, delta: int) -> None:
    """Step one setting through its choices, clamped at both ends."""
    setting = settings[selected]
    setting.index = max(0, min(len(setting.values) - 1, setting.index + delta))


def settings_lines(settings: list[Setting], selected: int, config) -> list[Line]:
    """The settings screen, laid out like the menu it came from."""
    lines: list[Line] = [(row, config.menu_title_color) for row in block_text("SETTINGS")]
    lines.append(("", config.menu_dim_color))
    rows = [
        f"{'>' if index == selected else ' '} {setting.label:<13} "
        f"{setting.shown():<11} {setting.blurb}"
        for index, setting in enumerate(settings)
    ]
    # Padded to a common width before they are centred. Centring each line on
    # its own length makes the label column zigzag, which is exactly what a
    # settings list must not do.
    width = max(len(row) for row in rows)
    for index, row in enumerate(rows):
        chosen = index == selected
        colour = config.menu_pick_color if chosen else config.menu_text_color
        lines.append((row.ljust(width), colour))
    lines.append(("", config.menu_dim_color))
    lines.append(("left/right change    esc back", config.menu_dim_color))
    return lines


def apply_settings(settings: list[Setting], config):
    """Fold the adjustable settings back into a Config."""
    from dataclasses import replace

    chosen = {setting.key: setting.value for setting in settings}
    strengths = dict(config.background_strength)
    visible = chosen.get("wash", strengths.get("visible", 0.44))
    strengths["visible"] = visible
    strengths["fresh"] = round(visible * 0.6, 3)
    strengths["stale"] = round(visible * 0.34, 3)
    return replace(
        config,
        background_strength=strengths,
        moss_chance=0.06 if chosen.get("moss", True) else 0.0,
        soak_workers=int(chosen.get("workers", config.soak_workers)),
        new_world_on_death=chosen.get("on_death") == "new world",
    )


def stored_values(settings: list[Setting]) -> dict:
    """The settings as a plain dict, ready to write to disk."""
    return {setting.key: setting.value for setting in settings}


def apply_stored(settings: list[Setting], stored: dict) -> None:
    """Move each setting to its remembered choice, ignoring anything stale.

    A value that is no longer offered - a worker count from a bigger machine,
    a colour step that has since been retuned - is skipped rather than being
    forced in, so an old settings file cannot put the menu into a state it
    cannot represent.
    """
    for setting in settings:
        value = stored.get(setting.key)
        if value in setting.values:
            setting.index = setting.values.index(value)


def soak_lines(status: str, results, config) -> list[Line]:
    """The soak screen: what it is doing, or what it found."""
    lines: list[Line] = [(row, config.menu_title_color) for row in block_text("SOAK")]
    lines.append(("", config.menu_dim_color))
    lines.append((status, config.menu_pick_color))
    lines.append(("", config.menu_dim_color))
    for stats in results or []:
        starved = 100.0 * stats.frontier_starved_ticks / max(1, stats.ticks)
        moved = 100.0 * stats.moved_ticks / max(1, stats.ticks)
        trouble = starved > 2.0 or moved < 80.0
        lines.append(
            (
                f"seed {stats.seed:<3} lvl {stats.final_level:<3} kills {stats.kills:<6}"
                f"reach {stats.max_distance:<6} moved {moved:5.1f}%  "
                f"starved {starved:5.1f}%",
                config.hud_bad_color if trouble else config.menu_text_color,
            )
        )
    if results:
        lines.append(("", config.menu_dim_color))
        lines.append(
            (
                "red means a world where the agent stalled or ran out of frontier",
                config.menu_dim_color,
            )
        )
    lines.append(("", config.menu_dim_color))
    lines.append(("esc back", config.menu_dim_color))
    return lines


# (heading, width, right-aligned) - the header and every row are built from
# this one spec, because hand-counting spaces to line up a header with its
# columns is a job that is never quite finished.
HALL_COLUMNS = (
    ("", 3, True),
    ("name", 22, False),
    ("level", 5, True),
    ("kills", 6, True),
    ("depth", 6, True),
    ("lived", 7, True),
    ("build", 16, False),
    ("killed by", 13, False),
    ("score", 6, True),
)


def _hall_row(cells) -> str:
    parts = []
    for (_, width, right), cell in zip(HALL_COLUMNS, cells):
        text = str(cell)
        parts.append(text.rjust(width) if right else text.ljust(width))
    return "  ".join(parts)


def hall_lines(entries, config) -> list[Line]:
    """The hall of fame, best run first.

    Ranked by score rather than any single number, so the columns show what
    went into it: a level that never left home reads differently from a modest
    one that reached the deep caverns.
    """
    from sim.hall import score

    lines: list[Line] = [(row, config.menu_title_color) for row in block_text("HALL")]
    lines.append(("", config.menu_dim_color))
    if not entries:
        lines.append(("nothing has died down there yet", config.menu_dim_color))
        lines.append(("", config.menu_dim_color))
        lines.append(("esc back", config.menu_dim_color))
        return lines

    lines.append(
        (_hall_row([heading for heading, _, _ in HALL_COLUMNS]), config.menu_dim_color)
    )
    for place, entry in enumerate(entries, start=1):
        colour = config.menu_pick_color if place == 1 else config.menu_text_color
        lines.append(
            (
                _hall_row(
                    [
                        f"{place}.",
                        (entry.name or "someone")[:22],
                        entry.level,
                        entry.kills,
                        entry.depth,
                        entry.ticks,
                        entry.archetype[:16],
                        entry.killer[:13],
                        score(entry),
                    ]
                ),
                colour,
            )
        )
    lines.append(("", config.menu_dim_color))
    lines.append(("esc back", config.menu_dim_color))
    return lines
