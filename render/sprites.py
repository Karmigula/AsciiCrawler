"""Turning a texture pack's files into things pygame can draw.

Kept apart from `render/packs.py` so the rules about what a pack *is* can be
tested without a display. This half needs a video mode to exist before it can
convert a surface, which is why it is lazy about everything: nothing is loaded
until the first time a glyph is actually drawn.

Two ways to draw, decided per sprite:

- **tinted** art is greyscale and gets multiplied by the cell colour. The
  colour already carries the fog tier, the biome wash and the threat tint, so
  tinted art inherits every one of those without the pack knowing they exist.
- **full** art is drawn as it is and only darkened, by how faded the cell
  colour is against full brightness. That is an approximation, and the right
  one: a remembered wall should look like a remembered wall whatever is drawn
  on it.

Scaled copies are cached per (glyph, size), because scaling a surface every
frame for every tile is the sort of thing that turns a smooth aquarium into a
slideshow.
"""

import pygame

from render.packs import Pack

# A sprite whose file turns out to be unreadable is remembered as a hole, so
# a broken PNG costs one failed load rather than one per frame forever.
_BROKEN = object()


class SpriteSheet:
    """Every picture in one pack, loaded on demand and kept.

    `for_glyph` is the whole interface: hand it a glyph and a cell size, get a
    surface or None. None means "draw the letter", which is what every glyph
    the pack does not mention gets.
    """

    def __init__(self, pack: Pack, cell_size: int) -> None:
        self.pack = pack
        self.cell_size = cell_size
        self._loaded: dict = {}
        self._scaled: dict = {}
        self.failures: list = []

    def resize(self, cell_size: int) -> None:
        """The window changed; the old scaled copies are the wrong size."""
        if cell_size == self.cell_size:
            return
        self.cell_size = cell_size
        self._scaled.clear()

    def mode_for(self, glyph: str) -> str | None:
        sprite = self.pack.sprite_for(glyph)
        return None if sprite is None else sprite.mode

    def for_glyph(self, glyph: str):
        """A surface scaled to the current cell, or None to draw the letter."""
        cached = self._scaled.get(glyph)
        if cached is not None:
            return None if cached is _BROKEN else cached

        surface = self._original(glyph)
        if surface is None:
            self._scaled[glyph] = _BROKEN
            return None

        size = self.cell_size
        if surface.get_size() != (size, size):
            # Nearest-neighbour: pack art is pixel art, and smoothing it turns
            # a crisp 16x16 wall into a smear at 20 pixels a cell.
            surface = pygame.transform.scale(surface, (size, size))
        self._scaled[glyph] = surface
        return surface

    def _original(self, glyph: str):
        """The file behind a glyph, loaded once, or None if it will not load."""
        if glyph in self._loaded:
            found = self._loaded[glyph]
            return None if found is _BROKEN else found

        sprite = self.pack.sprite_for(glyph)
        if sprite is None:
            self._loaded[glyph] = _BROKEN
            return None
        try:
            surface = pygame.image.load(str(sprite.path))
            surface = surface.convert_alpha()
        except (pygame.error, FileNotFoundError) as reason:
            # A pack must never be able to stop the game, so a bad file costs
            # that one glyph and is reported once.
            self.failures.append(f"{sprite.path.name} would not load: {reason}")
            self._loaded[glyph] = _BROKEN
            return None
        self._loaded[glyph] = surface
        return surface


def shade(surface, amount: float):
    """A copy of `surface` darkened to `amount` of its brightness.

    Used for `full` art on ground the creature is only remembering. Multiply
    blending keeps the alpha, so the shape of a sprite survives being dimmed -
    filling with black at low alpha would grey out the transparent parts and
    leave every sprite sitting on a smudge.
    """
    if amount >= 0.999:
        return surface
    level = max(0, min(255, int(255 * max(0.0, amount))))
    copy = surface.copy()
    copy.fill((level, level, level, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return copy


def tint(surface, colour):
    """A copy of `surface` multiplied by a colour.

    This is how a greyscale pack inherits everything the renderer already
    worked out: the cell colour carries the fog tier, the biome and whatever
    an overlay has done to it, so multiplying by it costs nothing and keeps a
    pack honest about the state of the world.
    """
    copy = surface.copy()
    copy.fill((*colour[:3], 255), special_flags=pygame.BLEND_RGBA_MULT)
    return copy
