"""The pygame window: a fixed-size glyph grid with a directly-following camera.

The only module besides main.py allowed to import pygame. It reads only the
state handed to it (cells of glyph+color pairs or None for blank, positions)
and never imports world/sim/agent modules.
"""

from collections.abc import Sequence
from pathlib import Path

import pygame

from config import Config

Color = tuple[int, int, int]
Position = tuple[int, int]

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Screen:
    """A terminal-looking window rendering one centered glyph per grid cell."""

    def __init__(self, config: Config) -> None:
        pygame.init()
        self._config = config
        self._window = pygame.display.set_mode((config.window_width, config.window_height))
        pygame.display.set_caption(config.window_title)
        self._font = self._load_font()
        self._hud_font = self._load_font(config.font_size - 2)
        self._glyph_cache: dict[tuple[str, Color], pygame.Surface] = {}
        self._cols = config.window_width // config.cell_size
        self._rows = config.window_height // config.cell_size
        self._margin_x = (config.window_width - self._cols * config.cell_size) // 2
        self._margin_y = (config.window_height - self._rows * config.cell_size) // 2

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
    ) -> None:
        """Draw a cell window; None cells stay blank.

        `cells` must be aligned with the camera window: its [0][0] entry is
        the world cell at `camera_origin(camera_center)` for the same camera
        later handed to `draw_glyph` — build it via `camera_origin` and
        `view_dims`. Only the handed state is read; rows beyond the view are
        clipped.
        """
        self._window.fill(self._config.background_color)
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
        x = config.window_width - width if right else 0
        y = 0 if top else config.window_height - height
        backing = pygame.Surface((width, height))
        backing.set_alpha(205)
        backing.fill(config.background_color)
        self._window.blit(backing, (x, y))
        for index, (text, color) in enumerate(lines):
            if not text:
                continue
            surface = self._hud_font.render(text, True, color)
            self._window.blit(surface, (x + 8, y + 6 + index * config.hud_line_height))

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
