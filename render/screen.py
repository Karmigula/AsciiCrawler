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

    def _load_font(self) -> pygame.font.Font:
        path = _REPO_ROOT / self._config.font_path
        if path.is_file():
            return pygame.font.Font(str(path), self._config.font_size)
        return pygame.font.Font(None, self._config.font_size)
