"""Draw the executable's icon: the creature, on a dark tile.

    .venv\\Scripts\\python.exe -m tools.make_icon

A default PyInstaller build wears PyInstaller's own icon, which tells the
person who downloaded the zip nothing about what they downloaded. This draws
`assets/icon.ico` from the same `@` the starter pack draws in the game, so the
taskbar and the title screen agree about what this is.

The .ico is assembled here rather than with Pillow, because an icon is a tiny
container format - a header, one directory entry per size, and a PNG for each
- and that is not worth a dependency the game does not otherwise have.
"""

import os
import struct
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from tools.make_starter_pack import creature  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "assets" / "icon.ico"

# Windows picks whichever of these fits the place it is drawing: 16 in a title
# bar, 32 in the taskbar, 256 on the desktop at large icon sizes.
SIZES = (16, 24, 32, 48, 64, 128, 256)

GROUND = (26, 24, 32, 255)
BODY = (236, 226, 190, 255)


def tile(size: int):
    """The creature on its own ground, at one size."""
    art = pygame.Surface((size, size), pygame.SRCALPHA)
    art.fill(GROUND)

    figure = creature()  # the starter pack's `@`, in greyscale
    # Tinted the way the game tints it, so the icon is the thing the player
    # will actually see rather than a grey approximation of it.
    figure = figure.copy()
    figure.fill(BODY, special_flags=pygame.BLEND_RGBA_MULT)

    inset = max(1, size // 8)
    span = size - inset * 2
    art.blit(pygame.transform.smoothscale(figure, (span, span)), (inset, inset))
    return art


def _png(surface) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    pygame.image.save(surface, buffer, "PNG")
    return buffer.getvalue()


def build() -> Path:
    pygame.init()
    pygame.display.set_mode((32, 32))

    images = [_png(tile(size)) for size in SIZES]

    # ICONDIR: reserved, type 1 (icon), how many images follow.
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, data in zip(SIZES, images):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,  # 0 means 256; a byte cannot hold it
            0 if size >= 256 else size,
            0,  # colours in the palette, 0 for a true-colour image
            0,  # reserved
            1,  # colour planes
            32,  # bits per pixel
            len(data),
            offset,
        )
        payload += data
        offset += len(data)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(header + entries + payload)
    return TARGET


def main() -> None:
    written = build()
    print(f"wrote {written} ({written.stat().st_size / 1024:.1f} KB)")
    print(f"{len(SIZES)} sizes: {', '.join(str(size) for size in SIZES)}")


if __name__ == "__main__":
    main()
