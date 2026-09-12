"""Draw the starter texture pack.

The sprites are generated rather than drawn by hand, for two reasons. A pack
made of committed PNGs nobody can regenerate is a dead end the first time the
cell size changes, and a worked example is more use than a pretty one: this
file is the answer to "how do I make a pack", and it is forty lines.

Everything here is greyscale, because greyscale is what `tinted` mode wants.
The renderer multiplies each sprite by the colour the cell already had, so
these shapes inherit the biome wash, the fog tier and any overlay without
knowing that any of that exists. Paint them in colour and they stop agreeing
with the rest of the screen.

    .venv\\Scripts\\python.exe tools/make_starter_pack.py
"""

import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

SIZE = 32
HERE = Path(__file__).resolve().parent.parent / "packs" / "starter"


def _surface():
    return pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)


def wall():
    """Courses of blocks, offset row to row."""
    art = _surface()
    art.fill((188, 188, 188, 255))
    mortar = (128, 128, 128, 255)
    for row in range(4):
        y = row * (SIZE // 4)
        pygame.draw.line(art, mortar, (0, y), (SIZE, y))
        shift = (SIZE // 4) if row % 2 else 0
        for column in range(2):
            x = (column * SIZE // 2 + shift) % SIZE
            pygame.draw.line(art, mortar, (x, y), (x, y + SIZE // 4))
    return art


def floor():
    """Flagstones: a dim square with a lighter edge."""
    art = _surface()
    art.fill((96, 96, 96, 255))
    pygame.draw.rect(art, (116, 116, 116, 255), (2, 2, SIZE - 4, SIZE - 4), 1)
    return art


def water():
    art = _surface()
    art.fill((150, 150, 150, 255))
    for row in range(3):
        y = 6 + row * 9
        pygame.draw.arc(art, (210, 210, 210, 255), (2, y, SIZE - 4, 10), 3.3, 6.1, 2)
    return art


def lava():
    art = _surface()
    art.fill((190, 190, 190, 255))
    for row in range(3):
        y = 7 + row * 9
        pygame.draw.arc(art, (245, 245, 245, 255), (2, y, SIZE - 4, 10), 3.3, 6.1, 3)
    return art


def ice():
    art = _surface()
    art.fill((170, 170, 170, 255))
    pygame.draw.line(art, (235, 235, 235, 255), (4, SIZE - 6), (SIZE - 6, 6), 2)
    pygame.draw.line(art, (235, 235, 235, 255), (10, SIZE - 4), (SIZE - 4, 12), 1)
    return art


def haze():
    art = _surface()
    for row in range(4):
        alpha = 70 + row * 18
        pygame.draw.ellipse(
            art, (200, 200, 200, alpha), (2, 3 + row * 7, SIZE - 4, 9)
        )
    return art


def gold():
    art = _surface()
    pygame.draw.circle(art, (235, 235, 235, 255), (13, 19), 6)
    pygame.draw.circle(art, (255, 255, 255, 255), (20, 14), 7)
    pygame.draw.circle(art, (170, 170, 170, 255), (20, 14), 7, 1)
    return art


def potion():
    art = _surface()
    pygame.draw.rect(art, (225, 225, 225, 255), (12, 6, 8, 5))
    pygame.draw.rect(art, (245, 245, 245, 255), (9, 11, 14, 16), border_radius=4)
    pygame.draw.rect(art, (160, 160, 160, 255), (9, 11, 14, 16), 1, border_radius=4)
    return art


SPRITES = {
    "#": ("wall.png", wall),
    ".": ("floor.png", floor),
    "~": ("water.png", water),
    "^": ("lava.png", lava),
    "_": ("ice.png", ice),
    "*": ("haze.png", haze),
    "$": ("gold.png", gold),
    "!": ("potion.png", potion),
}


def main() -> None:
    pygame.init()
    pygame.display.set_mode((SIZE, SIZE))
    HERE.mkdir(parents=True, exist_ok=True)

    for glyph, (name, draw) in SPRITES.items():
        pygame.image.save(draw(), str(HERE / name))

    manifest = {
        "name": "Starter",
        "cell_size": SIZE,
        "mode": "tinted",
        "sprites": {glyph: name for glyph, (name, _) in SPRITES.items()},
    }
    (HERE / "pack.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(SPRITES)} sprites and a manifest to {HERE}")
    print("everything else - monsters, totems, the creature - stays as letters.")


if __name__ == "__main__":
    main()
