"""The pygame window: a fixed-size glyph grid with a directly-following camera.

The only module besides main.py allowed to import pygame. It reads only the
state handed to it (cells of glyph+color pairs or None for blank, positions)
and never imports world/sim/agent modules.
"""

import os
from collections.abc import Sequence
from pathlib import Path

import pygame

from config import Config
from render.displays import monitor_rects

Color = tuple[int, int, int]
Position = tuple[int, int]

_REPO_ROOT = Path(__file__).resolve().parent.parent

def display_for_point(rects, x: int, y: int) -> int:
    """Index of the display containing a point, or the nearest one.

    Pure geometry, kept out of the class so it can be tested without a second
    monitor - which is the whole difficulty with this corner of the code.
    """
    for index, (left, top, width, height) in enumerate(rects):
        if left <= x < left + width and top <= y < top + height:
            return index
    if not rects:
        return 0
    # Nothing contains it: an offset layout, or a window dragged half off a
    # screen. Pick the display whose centre is closest.
    return min(
        range(len(rects)),
        key=lambda i: (rects[i][0] + rects[i][2] // 2 - x) ** 2
        + (rects[i][1] + rects[i][3] // 2 - y) ** 2,
    )


WINDOWED = "windowed"
BORDERLESS = "borderless"
FULLSCREEN = "fullscreen"


class Screen:
    """A terminal-looking window rendering one centered glyph per grid cell."""

    def __init__(self, config: Config) -> None:
        pygame.init()
        self._config = config
        pygame.display.set_caption(config.window_title)
        self._font = self._load_font()
        self._hud_font = self._load_font(config.font_size - 2)
        self._title_font = self._load_font(config.menu_title_font_size)
        self._glyph_cache: dict[tuple[str, Color], pygame.Surface] = {}
        self._mode = WINDOWED
        self._windowed = (config.window_width, config.window_height)
        self._display_bounds = self._probe_display_bounds()
        self._configure(self._windowed, pygame.RESIZABLE)

    def _configure(self, size: tuple[int, int], flags: int, display: int = 0) -> None:
        """Open the window at a size and recompute the glyph grid for it.

        A bigger window shows more world rather than a magnified slice of it -
        the glyph size is what the font is, and stretching it would make an
        ascii grid look like a photograph of one.
        """
        try:
            self._window = pygame.display.set_mode(size, flags, display=display)
        except (TypeError, pygame.error):
            # Older pygame builds have no `display` argument; the window then
            # opens wherever SDL chooses and `_place` moves it afterwards.
            self._window = pygame.display.set_mode(size, flags)
        self._width, self._height = self._window.get_size()
        cell = self._config.cell_size
        self._cols = max(1, self._width // cell)
        self._rows = max(1, self._height // cell)
        self._margin_x = (self._width - self._cols * cell) // 2
        self._margin_y = (self._height - self._rows * cell) // 2

    def resize(self, size: tuple[int, int]) -> None:
        """Handle the window being dragged to a new size."""
        if self._mode != FULLSCREEN:
            self._windowed = size
        self._configure(size, self._window.get_flags())

    def _desktop_sizes(self) -> list[tuple[int, int]]:
        try:
            sizes = pygame.display.get_desktop_sizes()
        except (AttributeError, pygame.error):
            sizes = []
        if sizes:
            return sizes
        info = pygame.display.Info()
        return [(info.current_w, info.current_h)]

    def _probe_display_bounds(self) -> list[tuple[int, int, int, int]] | None:
        """Measure where each display actually is, once, at startup.

        pygame reports display *sizes* but not their origins, and guessing that
        monitors run left to right in index order is wrong for stacked or
        offset arrangements. So measure instead: open a small hidden window on
        each display, ask where it landed, and work backwards. SDL centres it,
        so the display's origin is the window position minus half the leftover
        space.

        Done before the real window exists, so nothing flickers and it costs
        nothing during play. Returns None if the probe cannot run, and the
        caller falls back to the left-to-right guess.
        """
        # Ask the OS first. It knows, and every alternative is inference.
        # Monitors left of the primary sit at negative x, which no arrangement
        # of sizes alone can tell you about.
        reported = monitor_rects()
        if reported:
            return reported
        sizes = self._desktop_sizes()
        if len(sizes) <= 1:
            return [(0, 0, sizes[0][0], sizes[0][1])]
        probe = (64, 64)
        flags = pygame.NOFRAME | getattr(pygame, "HIDDEN", 0)
        bounds: list[tuple[int, int, int, int]] = []
        try:
            for index, (width, height) in enumerate(sizes):
                pygame.display.set_mode(probe, flags, display=index)
                position_x, position_y = pygame.display.get_window_position()
                bounds.append(
                    (
                        position_x - (width - probe[0]) // 2,
                        position_y - (height - probe[1]) // 2,
                        width,
                        height,
                    )
                )
        except (AttributeError, TypeError, pygame.error):
            return None
        return bounds

    def _display_rects(self) -> list[tuple[int, int, int, int]]:
        """(x, y, w, h) for each display, in index order.

        Three sources, best first: what the operating system says, what a
        startup probe measured, and finally a left-to-right guess that is only
        correct for the simplest desk.
        """
        if self._display_bounds:
            return self._display_bounds
        rects = []
        x = 0
        for width, height in self._desktop_sizes():
            rects.append((x, 0, width, height))
            x += width
        return rects

    def current_display(self) -> int:
        """Which display the window is mostly on, by its centre point."""
        rects = self._display_rects()
        try:
            window_x, window_y = pygame.display.get_window_position()
        except (AttributeError, pygame.error):
            return 0
        return display_for_point(
            rects, window_x + self._width // 2, window_y + self._height // 2
        )

    def _place(self, position: tuple[int, int]) -> None:
        """Move the window, if this pygame build can."""
        try:
            pygame.display.set_window_position(position)
        except (AttributeError, pygame.error):
            pass

    def _set_mode(self, mode: str) -> None:
        """Switch between windowed, borderless-windowed and fullscreen.

        Both borderless modes are placed explicitly on the display the window
        was already on, rather than left wherever SDL puts a new window. A
        borderless window that jumps to the primary monitor is worse than no
        borderless mode at all for something meant to sit on a second screen.
        """
        display = self.current_display()
        rects = self._display_rects()
        x, y, width, height = rects[min(display, len(rects) - 1)]
        self._mode = mode
        if mode == FULLSCREEN:
            # Sized and placed from the rectangle, not from a display index:
            # the index is only used to pick which rectangle, and SDL's
            # ordering need not agree with the operating system's.
            self._configure((width, height), pygame.NOFRAME, display=display)
            self._place((x, y))
        elif mode == BORDERLESS:
            # RESIZABLE as well as NOFRAME: dropping the border should not
            # take the drag handles with it. Fullscreen keeps NOFRAME alone,
            # since it already fills the display.
            self._configure(
                self._windowed, pygame.NOFRAME | pygame.RESIZABLE, display=display
            )
            self._place(
                (
                    x + max(0, (width - self._width) // 2),
                    y + max(0, (height - self._height) // 2),
                )
            )
        else:
            self._configure(self._windowed, pygame.RESIZABLE, display=display)
            self._place(
                (
                    x + max(0, (width - self._width) // 2),
                    y + max(0, (height - self._height) // 2),
                )
            )

    def toggle_fullscreen(self) -> None:
        """Borderless fullscreen filling the display the window is on.

        Borderless rather than exclusive: this is a thing to leave running on a
        second monitor, and an exclusive mode switch fights every other window
        on the machine for the display.
        """
        self._set_mode(WINDOWED if self._mode == FULLSCREEN else FULLSCREEN)

    def toggle_borderless(self) -> None:
        """A borderless window at the windowed size, centred on its display."""
        self._set_mode(WINDOWED if self._mode == BORDERLESS else BORDERLESS)

    @property
    def mode(self) -> str:
        """One of `windowed`, `borderless`, `fullscreen`."""
        return self._mode

    @property
    def size(self) -> tuple[int, int]:
        """Current window size in pixels."""
        return self._width, self._height

    @property
    def view_dims(self) -> tuple[int, int]:
        """The glyph-grid size of the view: (cols, rows)."""
        return self._cols, self._rows

    def camera_origin(self, camera_center: Position) -> Position:
        """World cell at the top-left corner of the view for this camera."""
        return self._origin(camera_center)

    def draw_cells(
        self,
        cells: Sequence[Sequence[tuple[str, Color] | None]],
        backgrounds: Sequence[Sequence[Color | None]] | None = None,
    ) -> None:
        """Draw a cell window; None cells stay blank.

        `backgrounds`, when given, is a matching grid of per-cell washes drawn
        under the glyphs - the biome colour lives there, because a glyph is too
        few pixels to carry it.

        `cells` must be aligned with the camera window: its [0][0] entry is
        the world cell at `camera_origin(camera_center)` for the same camera
        later handed to `draw_glyph` — build it via `camera_origin` and
        `view_dims`. Only the handed state is read; rows beyond the view are
        clipped.
        """
        self._window.fill(self._config.background_color)
        if backgrounds is not None:
            cell_size = self._config.cell_size
            for row, line in enumerate(backgrounds[: self._rows]):
                for col, color in enumerate(line[: self._cols]):
                    if color is None:
                        continue
                    self._window.fill(
                        color,
                        (
                            self._margin_x + col * cell_size,
                            self._margin_y + row * cell_size,
                            cell_size,
                            cell_size,
                        ),
                    )
        for row, line in enumerate(cells[: self._rows]):
            for col, cell in enumerate(line[: self._cols]):
                if cell is not None:
                    self._blit_glyph(cell[0], col, row, cell[1])

    def draw_glyph(
        self,
        glyph: str,
        cell_x: int,
        cell_y: int,
        camera_center: Position,
        color: Color,
    ) -> None:
        """Draw a single glyph at a world cell (e.g. the agent)."""
        origin_x, origin_y = self._origin(camera_center)
        self._blit_glyph(glyph, cell_x - origin_x, cell_y - origin_y, color)

    def draw_panel(self, lines, right: bool = True, top: bool = True) -> None:
        """Draw HUD lines in a corner over a dimmed backing.

        The backing is drawn rather than reserved: the world grid keeps the
        whole window, so the view does not jump when the HUD is toggled.
        """
        if not lines:
            return
        config = self._config
        height = len(lines) * config.hud_line_height + 12
        width = config.hud_panel_width
        x = self._width - width if right else 0
        y = 0 if top else self._height - height
        backing = pygame.Surface((width, height))
        backing.set_alpha(205)
        backing.fill(config.background_color)
        self._window.blit(backing, (x, y))
        for index, (text, color) in enumerate(lines):
            if not text:
                continue
            surface = self._hud_font.render(text, True, color)
            self._window.blit(surface, (x + 8, y + 6 + index * config.hud_line_height))

    def centered_capacity(self, big_lines: int = 0, reserved: int = 0) -> int:
        """How many ordinary lines `draw_centered` can show without spilling.

        It centres what it is given and starts at the top edge when that is
        too tall, so anything past the bottom is simply not on the screen.
        Callers with a list that grows - the hall of fame - ask first.
        """
        config = self._config
        title = big_lines * (config.hud_line_height + config.menu_title_font_size // 2)
        room = (self._height - title) // max(1, config.hud_line_height)
        return max(1, room - reserved)

    def draw_centered(self, lines, big_lines: int = 0) -> None:
        """Clear the window and draw lines centred in it, top down.

        Used for the title screen, which owns the whole window rather than
        sitting in a corner of it like the HUD panels do. The first
        `big_lines` are drawn in the title font, which is what makes the
        block-letter art read as a title rather than as more text.

        Centred vertically as well as horizontally: the block is measured
        first, so adding a menu entry does not leave the whole screen sitting
        too high.
        """
        config = self._config
        self._window.fill(config.background_color)
        heights = [
            config.hud_line_height + (config.menu_title_font_size // 2 if i < big_lines else 0)
            for i in range(len(lines))
        ]
        y = max(0, (self._height - sum(heights)) // 2)
        for index, (text, color) in enumerate(lines):
            font = self._title_font if index < big_lines else self._hud_font
            if text:
                surface = font.render(text, True, color)
                x = (self._width - surface.get_width()) // 2
                self._window.blit(surface, (x, y))
            y += heights[index]

    def panel_capacity(self, reserved_lines: int = 0) -> int:
        """How many lines a panel can show without running into a reserved block.

        The window is resizable, so two panels that sit comfortably in opposite
        corners at 800px can meet in the middle at 400. The one that yields is
        whichever the caller asks about.
        """
        per_line = max(1, self._config.hud_line_height)
        used = reserved_lines * per_line + 24
        return max(1, (self._height - used) // per_line)

    def screenshot(self, path) -> None:
        """Save the current frame to a png."""
        pygame.image.save(self._window, str(path))

    def present(self) -> None:
        pygame.display.flip()

    def close(self) -> None:
        pygame.quit()

    def _origin(self, camera_center: Position) -> Position:
        """World cell at the top-left corner of the view (direct follow, no smoothing)."""
        cx, cy = camera_center
        return cx - self._cols // 2, cy - self._rows // 2

    def _blit_glyph(self, glyph: str, col: int, row: int, color: Color) -> None:
        surface = self._glyph_surface(glyph, color)
        cell = self._config.cell_size
        px = self._margin_x + col * cell + (cell - surface.get_width()) // 2
        py = self._margin_y + row * cell + (cell - surface.get_height()) // 2
        self._window.blit(surface, (px, py))

    def _glyph_surface(self, glyph: str, color: Color) -> pygame.Surface:
        key = (glyph, color)
        if key not in self._glyph_cache:
            self._glyph_cache[key] = self._font.render(glyph, True, color)
        return self._glyph_cache[key]

    def _load_font(self, size: int | None = None) -> pygame.font.Font:
        size = self._config.font_size if size is None else size
        path = _REPO_ROOT / self._config.font_path
        if path.is_file():
            return pygame.font.Font(str(path), size)
        return pygame.font.Font(None, size)
