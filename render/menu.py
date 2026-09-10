"""The title screen: block-letter art and the menu, as lines of text.

Pygame-free and pure, like the HUD, so what the screen *says* can be tested
without opening a window. The block alphabet is spelled out here rather than
pulled from a figlet font: only eight letters are needed, and a table that
small is easier to read - and to adjust to the cell grid - than a dependency.

Only ASCII is used. The bundled font has box-drawing glyphs, but a title that
silently turns into tofu on a machine without them is a poor first impression,
and `#` is the same character the walls are drawn with.
"""

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
    ("quit", "close the window"),
)


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
        lines.append((f"{marker} {label:<10}  {blurb}", colour))

    lines.append(("", config.menu_dim_color))
    lines.append((f"world seed {seed}", config.menu_dim_color))
    lines.append(("up/down choose    enter start    esc quit", config.menu_dim_color))
    lines.append(("F10 borderless    F11 fullscreen", config.menu_dim_color))
    return lines


def move_selection(selected: int, delta: int) -> int:
    """Wrap the highlight around the entry list."""
    return (selected + delta) % len(ENTRIES)
