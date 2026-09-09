"""How frightening the agent believes a place to be.

Threat is read off memory, never off the world. The agent is afraid of the
troll it *saw*, standing where it *last saw it* — so it will flee a monster
that has already wandered off, and walk cheerfully into one that arrived after
it looked away. That is not a defect to be fixed; it is the same belief-vs-
truth rule the rest of the brain obeys, and it is where the interesting
behaviour comes from.

The field is a simple inverse-distance sum. It is sampled per candidate tile
during EXPLORE scoring and per neighbour during FLEE, so it has to be cheap:
it walks the remembered monsters near a point, not all of memory.
"""

from agent.memory import Memory
from config import Config
from sim.monsters import BY_GLYPH

Position = tuple[int, int]


def remembered_monsters(memory: Memory, near: Position, radius: int) -> list:
    """(position, kind) for every monster memory believes is within `radius`."""
    x, y = near
    found = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            coord = (x + dx, y + dy)
            glyph, _ = memory.snapshot(coord)
            if glyph is None:
                continue
            kind = BY_GLYPH.get(glyph)
            if kind is not None:
                found.append((coord, kind))
    return found


def danger(memory: Memory, coord: Position, config: Config) -> float:
    """Believed threat at a tile: inverse-distance sum over remembered monsters.

    Adjacency is what hurts, so the falloff is steep — a troll two tiles away
    prices at a third of a troll in your face.
    """
    total = 0.0
    for (mx, my), kind in remembered_monsters(memory, coord, config.threat_radius):
        distance = max(abs(mx - coord[0]), abs(my - coord[1]))
        total += kind.threat / (1.0 + distance)
    return total


def flee_threshold(stats, config: Config) -> float:
    """How much danger the agent will stand — less of it when it is hurt.

    A creature at a third of its hit points runs from a third of the threat it
    would have shrugged off at full health.
    """
    if stats is None or stats.max_hp <= 0:
        return config.flee_threat
    return config.flee_threat * (stats.hp / stats.max_hp)
