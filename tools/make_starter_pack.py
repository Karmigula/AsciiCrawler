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

For the creatures that means the colour is already spoken for: a monster is
tinted by how dangerous it is. So the shapes have to carry the identity on
their own, and every silhouette here is a different shape rather than the same
shape at a different size.

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
    """Flagstones, and brighter than they look here.

    Tinted art is multiplied, so a sprite's brightness is a *fraction* of the
    colour the cell already had - and floor colours are dark to begin with.
    Drawn at the dim grey a flagstone looks like on its own, the floor came
    out nearly black in game and the dungeon read as a void with a few lit
    squares in it. Greyscale art for multiply wants to sit near white and let
    the tint do the darkening.
    """
    art = _surface()
    art.fill((205, 205, 205, 255))
    pygame.draw.rect(art, (170, 170, 170, 255), (0, 0, SIZE, SIZE), 1)
    pygame.draw.line(art, (186, 186, 186, 255), (0, SIZE // 2), (SIZE, SIZE // 2))
    pygame.draw.line(art, (186, 186, 186, 255), (SIZE // 2, 0), (SIZE // 2, SIZE))
    return art


def water():
    art = _surface()
    art.fill((150, 150, 150, 255))
    for row in range(3):
        y = 6 + row * 9
        pygame.draw.arc(art, (210, 210, 210, 255), (2, y, SIZE - 4, 10), 3.3, 6.1, 2)
    return art


def lava():
    """Bubbles, not ripples.

    Water and lava were both drawn as a pair of arcs, which made them the same
    picture in two colours. Shape has to do the work: a colour-blind watcher,
    or one looking at a dim remembered tile, should still know which pool is
    the one that kills.
    """
    art = _surface()
    art.fill((175, 175, 175, 255))
    for x, y, r in ((9, 10, 4), (21, 14, 5), (13, 23, 4), (24, 25, 3)):
        pygame.draw.circle(art, (250, 250, 250, 255), (x, y), r)
        pygame.draw.circle(art, (120, 120, 120, 255), (x, y), r, 1)
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


# --- the living things -------------------------------------------------
#
# Drawn as silhouettes, and each one has to be a different silhouette. Tinted
# art is multiplied by the colour the cell already had, and a monster's colour
# is its threat, so at a glance the colour says how frightened to be and the
# shape says what it is. Two creatures that differ only in size become the
# same creature the moment one of them is standing in a dark corridor.
#
# The shading inside each shape is relative: multiply keeps ratios, so a
# highlight stays a highlight whatever colour the threat table hands over.

BODY = (235, 235, 235, 255)
EDGE = (150, 150, 150, 255)
DARK = (105, 105, 105, 255)


def creature():
    """The @: a walker with a pack on its back. Upright, and carrying something."""
    art = _surface()
    pygame.draw.circle(art, BODY, (16, 9), 5)               # head
    pygame.draw.polygon(art, BODY, [(11, 14), (21, 14), (23, 26), (9, 26)])
    pygame.draw.polygon(art, DARK, [(20, 15), (26, 17), (25, 24), (20, 23)])  # pack
    pygame.draw.line(art, EDGE, (12, 26), (11, 31), 3)      # legs
    pygame.draw.line(art, EDGE, (20, 26), (21, 31), 3)
    return art


def rat():
    """Low, long and tailed. The smallest thing that fights back."""
    art = _surface()
    pygame.draw.ellipse(art, BODY, (7, 17, 16, 9))
    pygame.draw.circle(art, BODY, (23, 19), 5)              # head, forward
    pygame.draw.polygon(art, EDGE, [(21, 15), (24, 11), (26, 16)])   # ear
    pygame.draw.line(art, EDGE, (7, 21), (2, 27), 2)        # tail
    pygame.draw.circle(art, DARK, (25, 18), 1)
    return art


def mite():
    """Round and legged: no head to speak of, which is the whole read."""
    art = _surface()
    for angle in range(0, 360, 45):
        from math import cos, radians, sin

        dx, dy = cos(radians(angle)), sin(radians(angle))
        pygame.draw.line(
            art, EDGE, (16 + dx * 6, 18 + dy * 6), (16 + dx * 13, 18 + dy * 13), 2
        )
    pygame.draw.circle(art, BODY, (16, 18), 7)
    pygame.draw.circle(art, DARK, (16, 18), 3)
    return art


def goblin():
    """Small and hunched, with ears swept up and back.

    Wide flat ears made a canopy over the head and the whole thing read as a
    mushroom. Angling them upward keeps the silhouette pointed instead of
    domed, which is the difference between a creature and a plant.
    """
    art = _surface()
    pygame.draw.polygon(art, BODY, [(11, 18), (21, 18), (23, 29), (9, 29)])  # hunched body
    pygame.draw.circle(art, BODY, (16, 13), 5)
    pygame.draw.polygon(art, EDGE, [(12, 12), (5, 3), (13, 10)])     # ears, up and back
    pygame.draw.polygon(art, EDGE, [(20, 12), (27, 3), (19, 10)])
    pygame.draw.circle(art, DARK, (14, 13), 1)
    pygame.draw.circle(art, DARK, (18, 13), 1)
    pygame.draw.line(art, DARK, (22, 20), (28, 28), 2)               # crooked knife
    return art


def orc():
    """Square shoulders with a neck: bulk, but bulk with a shape to it.

    Head and shoulders were one merged blob before, which made it an orc-sized
    smudge. The gap between them is what says "shoulders" at sixteen pixels.
    """
    art = _surface()
    pygame.draw.rect(art, BODY, (6, 17, 20, 12), border_radius=2)    # shoulders
    pygame.draw.circle(art, BODY, (16, 9), 6)                        # head, clear of them
    pygame.draw.polygon(art, DARK, [(12, 11), (13, 16), (15, 11)])   # tusks, below the jaw
    pygame.draw.polygon(art, DARK, [(20, 11), (19, 16), (17, 11)])
    # An axe, with a head on it. A bare vertical line read as a signpost.
    pygame.draw.line(art, EDGE, (27, 12), (27, 31), 2)
    pygame.draw.polygon(art, EDGE, [(27, 12), (20, 14), (27, 20)])
    return art


def ogre():
    """Huge and slack: a small head on a very large body."""
    art = _surface()
    pygame.draw.ellipse(art, BODY, (5, 13, 22, 18))
    pygame.draw.circle(art, BODY, (16, 8), 5)
    pygame.draw.circle(art, DARK, (13, 8), 1)
    pygame.draw.circle(art, DARK, (19, 8), 1)
    pygame.draw.line(art, EDGE, (5, 20), (1, 29), 4)                 # club arm
    return art


def troll():
    """Stooped, with heavy shoulders and knuckles near the ground.

    Straight arms splayed from a narrow body made an easel. Hanging them from
    shoulders that are wider than the head, with a bend and a fist at the end,
    is what makes the thing read as stooping rather than standing on struts.
    """
    art = _surface()
    pygame.draw.ellipse(art, BODY, (7, 11, 18, 12))                  # heavy shoulders
    pygame.draw.polygon(art, BODY, [(12, 20), (20, 20), (19, 30), (13, 30)])
    pygame.draw.circle(art, BODY, (16, 8), 4)                        # small sunken head
    pygame.draw.lines(art, EDGE, False, [(8, 15), (4, 23), (7, 28)], 3)
    pygame.draw.lines(art, EDGE, False, [(24, 15), (28, 23), (25, 28)], 3)
    pygame.draw.circle(art, EDGE, (7, 29), 3)                        # knuckles
    pygame.draw.circle(art, EDGE, (25, 29), 3)
    return art


def dragon():
    """Wings out: the widest thing in the game, so it reads first."""
    art = _surface()
    pygame.draw.polygon(art, EDGE, [(16, 16), (1, 7), (4, 20)])       # wings
    pygame.draw.polygon(art, EDGE, [(16, 16), (31, 7), (28, 20)])
    pygame.draw.ellipse(art, BODY, (11, 12, 10, 14))
    pygame.draw.circle(art, BODY, (16, 8), 4)
    pygame.draw.polygon(art, DARK, [(13, 5), (15, 1), (16, 5)])       # horns
    pygame.draw.polygon(art, DARK, [(19, 5), (17, 1), (16, 5)])
    return art


def sentry():
    """A floating eye in a ring. Nothing organic in the whole shape."""
    art = _surface()
    pygame.draw.circle(art, EDGE, (16, 16), 13, 2)
    pygame.draw.circle(art, BODY, (16, 16), 7)
    pygame.draw.circle(art, DARK, (16, 16), 3)
    return art


def construct():
    """Boxes inside boxes: built, and obviously built."""
    art = _surface()
    pygame.draw.rect(art, BODY, (7, 7, 18, 18))
    pygame.draw.rect(art, DARK, (12, 12, 8, 8))
    pygame.draw.line(art, EDGE, (10, 25), (10, 30), 3)
    pygame.draw.line(art, EDGE, (22, 25), (22, 30), 3)
    return art


def warden():
    """Tall, armoured, horned helm. The thing a station leaves on guard."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(10, 12), (22, 12), (24, 30), (8, 30)])
    pygame.draw.rect(art, BODY, (12, 3, 8, 9), border_radius=2)      # helm
    pygame.draw.polygon(art, EDGE, [(12, 4), (7, 1), (12, 9)])       # horns
    pygame.draw.polygon(art, EDGE, [(20, 4), (25, 1), (20, 9)])
    pygame.draw.line(art, DARK, (16, 14), (16, 29), 2)
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
    "@": ("creature.png", creature),
    "r": ("rat.png", rat),
    "x": ("mite.png", mite),
    "g": ("goblin.png", goblin),
    "o": ("orc.png", orc),
    "O": ("ogre.png", ogre),
    "T": ("troll.png", troll),
    "D": ("dragon.png", dragon),
    "S": ("sentry.png", sentry),
    "C": ("construct.png", construct),
    "W": ("warden.png", warden),
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
    print("totems, stalls and the named bosses stay as letters.")


if __name__ == "__main__":
    main()
