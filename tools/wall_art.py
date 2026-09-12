"""Fifteen walls, one per biome.

Rock is the one glyph the game draws more of than everything else put
together, and until now a pack drew it once for the whole world - so the
quarried halls and the frozen deep were the same brickwork under a different
wash. The wash was doing all the work, and a wash is a colour, which fog and
distance eat. A different *shape* survives both.

These live on their own sheet on purpose: fifteen variants of one glyph want
their own file, both to edit and to reason about. A manifest keys them as
`#@frozen` and falls back to plain `#` for any biome a pack has not bothered
with, so a pack may ship one wall, fifteen, or three.

Greyscale and bright, like everything else in `tinted` mode: the renderer
multiplies these by the colour the cell already had, so a wall painted
mid-grey comes out near black once the biome tint has had its turn. Bright
here means visible there.
"""

import random

import pygame

SIZE = 32
STONE = (198, 198, 198, 255)
LINE = (132, 132, 132, 255)
DEEP = (96, 96, 96, 255)
LIGHT = (238, 238, 238, 255)


def _surface(base=None):
    art = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    if base is not None:
        art.fill(base)
    return art


def _speckle(art, colour, count, seed, size=1):
    """Deterministic grain. Seeded so the sheet is the same every build."""
    dice = random.Random(seed)
    for _ in range(count):
        pygame.draw.rect(
            art, colour, (dice.randrange(SIZE), dice.randrange(SIZE), size, size)
        )
    return art


def halls():
    """Quarried courses, offset row to row. The mason's wall."""
    art = _surface(STONE)
    for row in range(4):
        y = row * 8
        pygame.draw.line(art, LINE, (0, y), (SIZE, y))
        shift = 8 if row % 2 else 0
        for column in range(2):
            x = (column * 16 + shift) % SIZE
            pygame.draw.line(art, LINE, (x, y), (x, y + 8))
    return art


def caves():
    """Wet rock: no courses at all, just lumps and drip lines."""
    art = _surface(STONE)
    for centre, radius in (((8, 9), 7), ((23, 7), 6), ((13, 24), 8), ((27, 22), 6)):
        pygame.draw.circle(art, LIGHT, centre, radius)
        pygame.draw.circle(art, LINE, centre, radius, 1)
    for x in (5, 17, 29):
        pygame.draw.line(art, DEEP, (x, 0), (x - 1, SIZE), 1)
    return art


def caverns():
    """Big boulders - the same rock as the caves, at four times the size."""
    art = _surface(STONE)
    for shape in (
        [(0, 6), (14, 0), (20, 14), (4, 19)],
        [(21, 3), (32, 9), (28, 22), (19, 16)],
        [(2, 21), (18, 18), (24, 32), (6, 32)],
    ):
        pygame.draw.polygon(art, LIGHT, shape)
        pygame.draw.polygon(art, LINE, shape, 1)
    return art


def ashfields():
    """Heat-cracked rock with ash drifted against the foot of it."""
    art = _surface(STONE)
    for start, end in (
        ((4, 0), (10, 14)),
        ((10, 14), (2, 24)),
        ((10, 14), (22, 18)),
        ((22, 18), (30, 8)),
        ((22, 18), (26, 32)),
    ):
        pygame.draw.line(art, DEEP, start, end, 2)
    pygame.draw.rect(art, LIGHT, (0, 26, SIZE, 6))
    _speckle(art, LINE, 40, seed=1)
    return art


def ossuary():
    """Walls of stacked skulls. Two dark sockets is all it takes to read."""
    art = _surface(STONE)
    for x, y in ((8, 9), (23, 9), (16, 24), (1, 24), (31, 24)):
        pygame.draw.circle(art, LIGHT, (x, y), 7)
        pygame.draw.circle(art, LINE, (x, y), 7, 1)
        pygame.draw.circle(art, DEEP, (x - 3, y - 1), 2)
        pygame.draw.circle(art, DEEP, (x + 3, y - 1), 2)
        pygame.draw.line(art, DEEP, (x, y + 3), (x, y + 6), 1)
    return art


def warren():
    """Dug earth, held together by roots."""
    art = _surface(STONE)
    for y in (6, 15, 25):
        points = [(x, y + (3 if (x // 4) % 2 else -3)) for x in range(0, SIZE + 4, 4)]
        pygame.draw.lines(art, DEEP, False, points, 2)
    for x in (10, 22):
        pygame.draw.line(art, LINE, (x, 0), (x, SIZE), 1)
    _speckle(art, LIGHT, 60, seed=2)
    return art


def ruins():
    """Brick with the top course gone, and vines growing in the gap."""
    art = _surface(STONE)
    for row in (2, 3):
        y = row * 8
        pygame.draw.line(art, LINE, (0, y), (SIZE, y))
        shift = 8 if row % 2 else 0
        for column in range(2):
            x = (column * 16 + shift) % SIZE
            pygame.draw.line(art, LINE, (x, y), (x, y + 8))
    # A jagged dark course where the top of the wall used to be. Cutting it
    # to transparent read better on the sheet and worse in the game: a wall
    # you can see the floor through looks like a gap you could walk into.
    pygame.draw.polygon(
        art, DEEP, [(0, 0), (SIZE, 0), (SIZE, 8), (22, 13), (12, 7), (0, 14)]
    )
    for x in (7, 20):
        points = [(x + (3 if (y // 5) % 2 else -3), y) for y in range(10, SIZE, 5)]
        pygame.draw.lines(art, DEEP, False, points, 2)
    return art


def marsh():
    """Rusted plate: rivets at the corners, streaks running down from them."""
    art = _surface(STONE)
    pygame.draw.rect(art, LINE, (0, 0, SIZE, SIZE), 2)
    pygame.draw.line(art, LINE, (0, 16), (SIZE, 16), 2)
    for x, y in ((5, 5), (26, 5), (5, 21), (26, 21)):
        pygame.draw.circle(art, DEEP, (x, y), 2)
        pygame.draw.line(art, DEEP, (x, y + 2), (x, y + 9), 1)
    _speckle(art, DEEP, 45, seed=3)
    return art


def crystal():
    """Facets: hard straight edges meeting at points, and very bright."""
    art = _surface(LINE)
    for shape in (
        [(0, 0), (16, 4), (10, 18), (0, 14)],
        [(16, 4), (32, 0), (32, 13), (20, 17)],
        [(10, 18), (22, 16), (26, 32), (8, 32)],
        [(0, 15), (9, 19), (6, 32), (0, 32)],
        [(26, 18), (32, 15), (32, 32), (27, 32)],
    ):
        pygame.draw.polygon(art, LIGHT, shape)
        pygame.draw.polygon(art, DEEP, shape, 1)
    return art


def frozen():
    """Ice: bright slabs with long fractures running through them."""
    art = _surface(LIGHT)
    for x in (7, 16, 25):
        pygame.draw.line(art, DEEP, (x, 0), (x + 2, SIZE), 2)
    for y in (11, 23):
        pygame.draw.line(art, DEEP, (0, y), (SIZE, y - 2), 2)
    # Fractures across the slabs, or the whole tile is a white square and the
    # ice reads as a hole in the wall rather than a wall made of ice.
    for start, end in (((7, 11), (16, 3)), ((16, 22), (25, 13)), ((1, 29), (9, 21))):
        pygame.draw.line(art, LINE, start, end, 2)
    return art


def spores():
    """Wall gone over with caps - rings, not blobs, so it is not the caves."""
    art = _surface(STONE)
    for (x, y), radius in (((7, 8), 5), ((22, 6), 4), ((26, 20), 6), ((10, 23), 5)):
        pygame.draw.circle(art, LIGHT, (x, y), radius)
        pygame.draw.circle(art, DEEP, (x, y), radius, 1)
        pygame.draw.circle(art, DEEP, (x, y), max(1, radius - 3))
    _speckle(art, LIGHT, 50, seed=4)
    return art


def sunken():
    """Cathedral masonry: an arch, and a waterline across it."""
    art = _surface(STONE)
    pygame.draw.rect(art, LINE, (0, 0, SIZE, SIZE), 1)
    pygame.draw.arc(art, DEEP, (4, 4, 24, 34), 0.0, 3.15, 3)
    pygame.draw.line(art, DEEP, (4, 21), (4, 32), 2)
    pygame.draw.line(art, DEEP, (27, 21), (27, 32), 2)
    pygame.draw.line(art, LIGHT, (0, 12), (SIZE, 12), 2)
    pygame.draw.line(art, LIGHT, (0, 15), (SIZE, 15), 1)
    return art


def station():
    """A panel, a seam down the middle of it, and a grille."""
    art = _surface(STONE)
    pygame.draw.rect(art, DEEP, (0, 0, SIZE, SIZE), 2)
    pygame.draw.line(art, DEEP, (16, 0), (16, SIZE), 2)
    for y in range(6, 28, 5):
        pygame.draw.line(art, LINE, (20, y), (28, y), 2)
    pygame.draw.rect(art, LIGHT, (4, 6, 8, 8))
    pygame.draw.rect(art, DEEP, (4, 6, 8, 8), 1)
    return art


def machine():
    """Pipework, with a wheel on it."""
    art = _surface(STONE)
    pygame.draw.line(art, DEEP, (0, 8), (SIZE, 8), 4)
    pygame.draw.line(art, DEEP, (0, 26), (SIZE, 26), 4)
    pygame.draw.line(art, DEEP, (24, 8), (24, 26), 3)
    pygame.draw.circle(art, LIGHT, (10, 18), 7)
    pygame.draw.circle(art, DEEP, (10, 18), 7, 2)
    pygame.draw.circle(art, DEEP, (10, 18), 2)
    for spoke in ((0, -7), (0, 7), (-7, 0), (7, 0)):
        pygame.draw.line(art, DEEP, (10, 18), (10 + spoke[0], 18 + spoke[1]), 1)
    return art


def weave():
    """Over, under, over: a lattice, not a grid."""
    art = _surface(DEEP)
    for x in range(2, SIZE, 8):
        pygame.draw.rect(art, STONE, (x, 0, 5, SIZE))
    # The weft only shows in the gaps between warp threads on alternate rows,
    # which is what makes this a weave and not a set of stripes: the bright
    # thread passes behind one column and in front of the next.
    for index, y in enumerate(range(2, SIZE, 8)):
        pygame.draw.rect(art, LIGHT, (0, y, SIZE, 5))
        for x in range(2 if index % 2 else 10, SIZE, 16):
            pygame.draw.rect(art, STONE, (x, y, 5, 5))
    return art


# In biome order, which is the order the sheet is laid out in. Adding a biome
# appends a cell and moves nothing already in the file.
WALLS = {
    "halls": halls,
    "caves": caves,
    "caverns": caverns,
    "ashfields": ashfields,
    "ossuary": ossuary,
    "warren": warren,
    "ruins": ruins,
    "marsh": marsh,
    "crystal": crystal,
    "frozen": frozen,
    "spores": spores,
    "sunken": sunken,
    "station": station,
    "machine": machine,
    "weave": weave,
}
