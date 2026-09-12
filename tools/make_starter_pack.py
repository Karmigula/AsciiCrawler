"""Draw the starter texture pack.

The sprites are generated rather than drawn by hand, for two reasons. A pack
made of committed PNGs nobody can regenerate is a dead end the first time the
cell size changes, and a worked example is more use than a pretty one: this
file is the answer to "how do I make a pack".

Fifty-one of them, which is every glyph the game can draw. That is not a
requirement - a pack covering only walls is a perfectly good pack, and the
renderer falls back to letters glyph by glyph - it is just what this one
grew into. Each sprite is one short function, so the useful way to read this
file is to find the thing you want to replace and copy that function.

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


# --- gear, props and the marks a spell leaves ------------------------------


def weapon():
    """A sword, point up. The one item shape everybody already knows."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(16, 2), (19, 8), (19, 22), (13, 22), (13, 8)])
    pygame.draw.rect(art, EDGE, (8, 22, 16, 3))                      # crossguard
    pygame.draw.rect(art, DARK, (14, 25, 4, 6))                      # grip
    return art


def armor():
    """A breastplate: shoulders wider than waist, and a neck cut out of it."""
    art = _surface()
    pygame.draw.polygon(
        art, BODY, [(6, 8), (13, 6), (19, 6), (26, 8), (23, 28), (9, 28)]
    )
    pygame.draw.polygon(art, DARK, [(13, 6), (19, 6), (16, 12)])     # collar
    pygame.draw.line(art, EDGE, (16, 13), (16, 27), 1)
    return art


def ring():
    """A band seen face on, with a stone. Small, and a hole in the middle."""
    art = _surface()
    pygame.draw.circle(art, BODY, (16, 19), 9, 4)
    pygame.draw.polygon(art, EDGE, [(16, 3), (21, 9), (16, 14), (11, 9)])
    return art


def amulet():
    """A pendant on a cord: the cord is what tells it from a ring."""
    art = _surface()
    pygame.draw.arc(art, EDGE, (8, 2, 16, 16), 0.3, 2.9, 2)          # cord
    pygame.draw.polygon(art, BODY, [(16, 13), (23, 20), (16, 29), (9, 20)])
    pygame.draw.circle(art, DARK, (16, 20), 3)
    return art


def grave():
    """A headstone in the ground. Somebody's whole run, in one tile."""
    art = _surface()
    pygame.draw.rect(art, BODY, (9, 8, 14, 19), border_top_left_radius=7,
                     border_top_right_radius=7)
    pygame.draw.line(art, DARK, (16, 13), (16, 22), 2)               # a cross on it
    pygame.draw.line(art, DARK, (12, 16), (20, 16), 2)
    pygame.draw.rect(art, EDGE, (5, 27, 22, 4))                      # turned earth
    return art


def totem():
    """A carved post. Deliberately face-like: it is a thing you ask."""
    art = _surface()
    pygame.draw.rect(art, BODY, (10, 4, 12, 26))
    pygame.draw.circle(art, DARK, (13, 11), 2)                       # eyes
    pygame.draw.circle(art, DARK, (19, 11), 2)
    pygame.draw.arc(art, DARK, (11, 15, 10, 8), 3.4, 6.0, 2)         # mouth
    pygame.draw.rect(art, EDGE, (6, 4, 20, 3))                       # cap
    return art


def stall():
    """An awning over a counter. Somewhere to stand and spend."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(2, 12), (30, 12), (26, 4), (6, 4)])   # awning
    for x in range(4, 28, 6):
        pygame.draw.line(art, DARK, (x, 12), (x + 2, 4), 2)                # stripes
    pygame.draw.rect(art, EDGE, (6, 16, 20, 4))                            # counter
    pygame.draw.line(art, EDGE, (8, 20), (8, 30), 2)
    pygame.draw.line(art, EDGE, (24, 20), (24, 30), 2)
    return art


def _bolt(start, end):
    """A streak across the tile: bright in the middle, thin at the ends."""
    art = _surface()
    pygame.draw.line(art, EDGE, start, end, 7)
    pygame.draw.line(art, BODY, start, end, 3)
    pygame.draw.line(art, (255, 255, 255, 255), start, end, 1)
    return art


def bolt_flat():
    return _bolt((0, 16), (32, 16))


def bolt_upright():
    return _bolt((16, 0), (16, 32))


def bolt_rising():
    return _bolt((0, 31), (31, 0))


def bolt_falling():
    return _bolt((0, 0), (31, 31))


# --- the named things ------------------------------------------------------
#
# Twenty-one of them, and the temptation was to draw one grand figure and swap
# a badge on its chest. That would have read as "a boss" instantly and as
# *which* boss never, and the silhouette test would have caught it: twenty-one
# shapes that are ninety per cent the same mask.
#
# So they are grouped by what they are rather than by how important they are -
# beasts, growing things, the dead, machines, crowned figures - and each group
# has its own outline. Boss-ness comes through anyway, because they are all
# bigger than the tile's monsters and drawn to its edges.


def houndmaster():
    """A hound, low and four-legged, head up."""
    art = _surface()
    pygame.draw.ellipse(art, BODY, (6, 12, 20, 11))
    pygame.draw.circle(art, BODY, (25, 9), 5)
    pygame.draw.polygon(art, EDGE, [(23, 5), (26, 1), (28, 6)])
    for x in (9, 14, 19, 24):
        pygame.draw.line(art, EDGE, (x, 22), (x, 30), 2)
    pygame.draw.line(art, EDGE, (6, 15), (1, 9), 2)
    return art


def tunnelking():
    """A worm arching out of the floor and back into it."""
    art = _surface()
    pygame.draw.arc(art, BODY, (2, 6, 28, 34), 0.25, 2.9, 9)
    pygame.draw.circle(art, BODY, (26, 16), 5)
    pygame.draw.circle(art, DARK, (26, 16), 2)
    return art


def deepmother():
    """A bulb on many legs. The legs are most of the shape."""
    art = _surface()
    for dx in (-14, -9, 9, 14):
        pygame.draw.lines(art, EDGE, False, [(16, 16), (16 + dx, 10), (16 + dx, 28)], 2)
    pygame.draw.ellipse(art, BODY, (8, 8, 16, 18))
    pygame.draw.circle(art, DARK, (13, 14), 2)
    pygame.draw.circle(art, DARK, (19, 14), 2)
    return art


def cinderwake():
    """Tongues of flame with gaps between them, over a narrow base.

    A solid triangle of fire is the same mask as a king in a cape, which is
    not a sentence anybody wants to have to write. Licking flames have air in
    them, and that is what makes the outline fire rather than fabric.
    """
    art = _surface()
    pygame.draw.polygon(art, BODY, [(16, 1), (21, 14), (16, 20), (11, 14)])
    pygame.draw.polygon(art, EDGE, [(7, 9), (12, 19), (7, 25), (3, 18)])
    pygame.draw.polygon(art, EDGE, [(25, 9), (29, 18), (25, 25), (20, 19)])
    pygame.draw.polygon(art, BODY, [(16, 18), (23, 27), (16, 31), (9, 27)])
    pygame.draw.circle(art, DARK, (16, 26), 3)
    return art


def bonewright():
    """A ribcage on legs: more gap than body."""
    art = _surface()
    pygame.draw.circle(art, BODY, (16, 7), 5)
    pygame.draw.line(art, BODY, (16, 12), (16, 26), 3)
    for y in range(14, 26, 4):
        pygame.draw.arc(art, EDGE, (7, y - 4, 18, 9), 3.4, 6.0, 2)
    pygame.draw.line(art, EDGE, (13, 26), (11, 31), 2)
    pygame.draw.line(art, EDGE, (19, 26), (21, 31), 2)
    return art


def sporelord():
    """A cap on a stalk. Wide top, narrow bottom."""
    art = _surface()
    pygame.draw.ellipse(art, BODY, (2, 6, 28, 15))
    pygame.draw.rect(art, EDGE, (12, 19, 8, 12))
    for x in (8, 16, 24):
        pygame.draw.circle(art, DARK, (x, 12), 2)
    return art


def greenhusk():
    """A broad figure with leaves for shoulders."""
    art = _surface()
    pygame.draw.polygon(art, EDGE, [(16, 12), (1, 8), (6, 18)])
    pygame.draw.polygon(art, EDGE, [(16, 12), (31, 8), (26, 18)])
    pygame.draw.polygon(art, BODY, [(11, 6), (21, 6), (24, 30), (8, 30)])
    pygame.draw.line(art, DARK, (16, 10), (16, 28), 2)
    return art


def rustsaint():
    """Almost all halo: a huge ring with very little underneath it."""
    art = _surface()
    pygame.draw.circle(art, EDGE, (16, 12), 13, 3)
    pygame.draw.circle(art, BODY, (16, 12), 4)
    pygame.draw.line(art, BODY, (16, 16), (16, 30), 3)               # a thin stem
    pygame.draw.line(art, EDGE, (9, 22), (23, 22), 2)                # arms, straight out
    return art


def prism():
    """Floating angles: nothing here touches the ground."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(16, 2), (27, 16), (16, 30), (5, 16)])
    pygame.draw.polygon(art, DARK, [(16, 9), (22, 16), (16, 23), (10, 16)])
    pygame.draw.line(art, EDGE, (5, 16), (27, 16), 1)
    return art


def hoarfrost():
    """One great spire off-centre, with the rest of the field beneath it.

    Three even peaks are also three hooded figures, and the Drowned Choir got
    there first. Asymmetry and a solid base are what tell a glacier from a
    congregation.
    """
    art = _surface()
    pygame.draw.polygon(art, BODY, [(11, 1), (20, 24), (3, 24)])     # the big one
    pygame.draw.polygon(art, EDGE, [(24, 10), (30, 24), (18, 24)])
    pygame.draw.rect(art, BODY, (1, 23, 30, 8))                      # solid ground
    return art


def bloomtyrant():
    """A flower with too many petals, and something in the middle."""
    art = _surface()
    from math import cos, radians, sin

    for angle in range(0, 360, 45):
        dx, dy = cos(radians(angle)), sin(radians(angle))
        pygame.draw.circle(art, EDGE, (int(16 + dx * 9), int(14 + dy * 9)), 5)
    pygame.draw.circle(art, BODY, (16, 14), 6)
    pygame.draw.circle(art, DARK, (16, 14), 3)
    pygame.draw.line(art, EDGE, (16, 20), (16, 31), 3)
    return art


def drownedchoir():
    """Three hooded shapes with daylight between them.

    Drawn overlapping they merged into one figure and the whole point - that
    it is a choir rather than a singer - was lost. Narrower, further apart,
    and at three different heights so the outline has three peaks in it.
    """
    art = _surface()
    for x, top, shade in ((6, 15, EDGE), (26, 13, EDGE), (16, 5, BODY)):
        pygame.draw.polygon(
            art, shade,
            [(x - 4, 31), (x - 4, top + 5), (x, top), (x + 4, top + 5), (x + 4, 31)],
        )
        pygame.draw.circle(art, DARK, (x, top + 6), 2)
    return art


def overseer():
    """One eye on a tripod. Built to watch, and not much else."""
    art = _surface()
    pygame.draw.circle(art, BODY, (16, 11), 9)
    pygame.draw.circle(art, DARK, (16, 11), 4)
    for x in (7, 16, 25):
        pygame.draw.line(art, EDGE, (16, 19), (x, 31), 2)
    return art


def enginehead():
    """A boxy thing with pistons for arms."""
    art = _surface()
    pygame.draw.rect(art, BODY, (9, 8, 14, 16))
    pygame.draw.rect(art, DARK, (13, 12, 6, 6))
    pygame.draw.rect(art, EDGE, (2, 12, 7, 5))
    pygame.draw.rect(art, EDGE, (23, 12, 7, 5))
    pygame.draw.line(art, EDGE, (12, 24), (11, 31), 3)
    pygame.draw.line(art, EDGE, (20, 24), (21, 31), 3)
    return art


def loomwarden():
    """A figure with threads running off it in every direction."""
    art = _surface()
    from math import cos, radians, sin

    for angle in range(0, 360, 30):
        dx, dy = cos(radians(angle)), sin(radians(angle))
        pygame.draw.line(art, EDGE, (16, 16), (16 + dx * 16, 16 + dy * 16), 1)
    pygame.draw.polygon(art, BODY, [(16, 5), (24, 16), (16, 27), (8, 16)])
    pygame.draw.circle(art, DARK, (16, 16), 3)
    return art


def crownless():
    """Seated on a throne it has no crown for: a wide silhouette, not a tall one.

    Standing, it was the same shape as the Ash King and the Ossuarch to within
    a fifth of its pixels. Sitting is the difference - the throne makes the
    outline square and bottom-heavy where every other royal thing is a column.
    """
    art = _surface()
    pygame.draw.rect(art, EDGE, (3, 4, 26, 27))                      # throne back
    pygame.draw.rect(art, DARK, (3, 4, 26, 27), 2)
    pygame.draw.polygon(art, BODY, [(11, 12), (21, 12), (24, 29), (8, 29)])
    pygame.draw.circle(art, BODY, (16, 9), 4)
    pygame.draw.line(art, DARK, (10, 3), (13, 3), 2)                 # a crown, broken
    pygame.draw.line(art, DARK, (19, 3), (22, 3), 2)
    return art


def stonemother():
    """A seated boulder with a face. Wider than it is tall."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(2, 31), (6, 14), (26, 14), (30, 31)])
    pygame.draw.circle(art, BODY, (16, 11), 7)
    pygame.draw.circle(art, DARK, (13, 10), 2)
    pygame.draw.circle(art, DARK, (19, 10), 2)
    pygame.draw.line(art, DARK, (8, 22), (24, 22), 2)
    return art


def ashking():
    """Crowned, caped, and standing still."""
    art = _surface()
    pygame.draw.polygon(art, EDGE, [(5, 16), (27, 16), (24, 31), (8, 31)])   # cape
    pygame.draw.polygon(art, BODY, [(12, 13), (20, 13), (22, 31), (10, 31)])
    pygame.draw.circle(art, BODY, (16, 9), 5)
    pygame.draw.polygon(art, EDGE, [(10, 5), (12, 1), (14, 5), (16, 1), (18, 5),
                                    (20, 1), (22, 5)])               # crown
    return art


def ossuarch():
    """A robe flared into a triangle, and a staff taller than it is."""
    art = _surface()
    pygame.draw.polygon(art, BODY, [(16, 12), (28, 31), (4, 31)])    # robe, wide at the foot
    pygame.draw.circle(art, BODY, (16, 9), 5)
    pygame.draw.circle(art, DARK, (14, 8), 2)
    pygame.draw.circle(art, DARK, (18, 8), 2)
    pygame.draw.line(art, EDGE, (29, 1), (29, 31), 3)                # staff, full height
    pygame.draw.circle(art, EDGE, (29, 3), 3)
    return art


def winterjaw():
    """Jaws seen from the side, hinged at the back and open wide.

    Two horizontal plates with teeth between them read as a portico however
    the teeth were shaped - the giveaway is that architecture is symmetrical
    about a vertical line and a mouth is not. Hinging both jaws at the right
    and opening them to the left breaks that symmetry, and it stops looking
    like a building.
    """
    art = _surface()
    pygame.draw.polygon(art, BODY, [(30, 15), (3, 2), (1, 9), (27, 17)])   # upper jaw
    pygame.draw.polygon(art, BODY, [(30, 17), (3, 30), (1, 23), (27, 15)]) # lower jaw
    for at, (x, y) in enumerate(((6, 7), (11, 9), (16, 11), (21, 13))):
        pygame.draw.polygon(art, EDGE, [(x, y), (x + 2, y + 6), (x + 4, y + 1)])
    for at, (x, y) in enumerate(((6, 25), (11, 23), (16, 21), (21, 19))):
        pygame.draw.polygon(art, EDGE, [(x, y), (x + 2, y - 6), (x + 4, y - 1)])
    pygame.draw.circle(art, DARK, (28, 16), 3)                             # hinge
    return art


def firstengine():
    """A cog with a core: the oldest machine down there."""
    art = _surface()
    from math import cos, radians, sin

    for angle in range(0, 360, 45):
        dx, dy = cos(radians(angle)), sin(radians(angle))
        pygame.draw.circle(art, EDGE, (int(16 + dx * 13), int(16 + dy * 13)), 4)
    pygame.draw.circle(art, BODY, (16, 16), 11)
    pygame.draw.circle(art, DARK, (16, 16), 5)
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
    ")": ("weapon.png", weapon),
    "[": ("armor.png", armor),
    "=": ("ring.png", ring),
    '"': ("amulet.png", amulet),
    "+": ("grave.png", grave),
    "&": ("totem.png", totem),
    "%": ("stall.png", stall),
    "-": ("bolt_flat.png", bolt_flat),
    "|": ("bolt_upright.png", bolt_upright),
    "/": ("bolt_rising.png", bolt_rising),
    "\\": ("bolt_falling.png", bolt_falling),
    # The named things
    "H": ("houndmaster.png", houndmaster),
    "K": ("tunnelking.png", tunnelking),
    "M": ("deepmother.png", deepmother),
    "F": ("cinderwake.png", cinderwake),
    "B": ("bonewright.png", bonewright),
    "P": ("sporelord.png", sporelord),
    "G": ("greenhusk.png", greenhusk),
    "R": ("rustsaint.png", rustsaint),
    "Y": ("prism.png", prism),
    "Z": ("hoarfrost.png", hoarfrost),
    "L": ("bloomtyrant.png", bloomtyrant),
    "N": ("drownedchoir.png", drownedchoir),
    "V": ("overseer.png", overseer),
    "E": ("enginehead.png", enginehead),
    "U": ("loomwarden.png", loomwarden),
    "A": ("crownless.png", crownless),
    "Q": ("stonemother.png", stonemother),
    "X": ("ashking.png", ashking),
    "J": ("ossuarch.png", ossuarch),
    "I": ("winterjaw.png", winterjaw),
    "0": ("firstengine.png", firstengine),
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
    print("that is every glyph the game draws.")


if __name__ == "__main__":
    main()
