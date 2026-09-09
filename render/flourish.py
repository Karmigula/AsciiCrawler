"""Cosmetic speckle: moss on old stone. Pure, pygame-free, no game meaning.

Deterministic from world position, so a given tile is mossy for the life of
the world and does not shimmer as the camera moves - the one property a purely
decorative effect still has to get right.
"""

Color = tuple[int, int, int]

_MASK = (1 << 32) - 1


def _hash(x: int, y: int, salt: int = 0x9E3779B1) -> float:
    """A stable 0.0-1.0 value for a world coordinate."""
    h = (x * 0x1F1F1F1F) ^ (y * 0x27220A95) ^ salt
    h &= _MASK
    h ^= h >> 16
    h = (h * 0x7FEB352D) & _MASK
    h ^= h >> 15
    return (h & 0xFFFF) / 0xFFFF


def _blend(a: Color, b: Color, weight: float) -> Color:
    return (
        round(a[0] + (b[0] - a[0]) * weight),
        round(a[1] + (b[1] - a[1]) * weight),
        round(a[2] + (b[2] - a[2]) * weight),
    )


def speckle_moss(grid, origin, floor_glyph: str, config):
    """Tint a seeded scattering of floor tiles toward moss green."""
    if config.moss_chance <= 0:
        return grid
    ox, oy = origin
    out = []
    for y, row in enumerate(grid):
        line = []
        for x, cell in enumerate(row):
            if cell is None or cell[0] != floor_glyph:
                line.append(cell)
                continue
            noise = _hash(x + ox, y + oy)
            if noise >= config.moss_chance:
                line.append(cell)
                continue
            # Weight by how far into the mossy band it fell, so patches have
            # soft edges instead of every mossy tile being identical.
            weight = 0.35 + 0.45 * (noise / config.moss_chance)
            line.append((cell[0], _blend(cell[1], config.moss_color, weight)))
        out.append(line)
    return out
