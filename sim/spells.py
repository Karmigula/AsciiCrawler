"""Ranged attacks: what a focus lets the creature do from across a room.

A spell is the first thing in this game the agent can do to something it is
not standing next to, which is a bigger change than it sounds. Everything
before it - bump to attack, flee when frightened - assumed the only question
about a monster was whether to be beside it. A spell makes distance a choice
worth having, and `agent.kiter` is what makes that choice.

Cooldowns are counted in ticks on the agent, not on the spell, because the
table is shared and the creature is not. A spell nobody can reach is just a
row here; what makes it real is an affix on something it picked up.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Spell:
    """One ranged attack.

    `reach` is in tiles, Chebyshev, matching how everything else here measures
    distance. `inflicts` names a monster effect, which is how a small creature
    with the right trinket can wear down something far bigger than it: chilled
    things move slower, withered things hit softer.

    Cooldowns are long on purpose. A spell that comes back in a dozen ticks is
    just a better melee attack, and the gap between casts is the whole reason
    backing away is worth doing.
    """

    key: str
    label: str
    reach: int
    damage: int
    cooldown: int
    cost: int = 0
    inflicts: str = ""


SPELLS: tuple[Spell, ...] = (
    Spell("ember_bolt", "ember bolt", reach=6, damage=9, cooldown=55, cost=8),
    Spell("frost_lance", "frost lance", reach=5, damage=5, cooldown=45, cost=6,
          inflicts="chilled"),
    Spell("withering", "withering", reach=5, damage=4, cooldown=60, cost=7,
          inflicts="withered"),
    Spell("spark", "spark", reach=4, damage=4, cooldown=30, cost=3),
)

BY_KEY = {spell.key: spell for spell in SPELLS}

# What a bolt looks like in flight, by the direction it is travelling. The
# classic roguelike answer, and the right one: a line of dashes reads as
# something crossing the room in a way a lit tile does not.
BOLT_GLYPHS = {
    (1, 0): "-", (-1, 0): "-",
    (0, 1): "|", (0, -1): "|",
    (1, 1): "\\", (-1, -1): "\\",
    (1, -1): "/", (-1, 1): "/",
}


def trail(origin, target) -> list:
    """The tiles a bolt crosses, from just after the caster to the target.

    Straight enough to read: the same Bresenham line the eye expects, so the
    bolt appears to come from the creature rather than materialise near it.
    The caster's own tile is left out - the agent is standing there.
    """
    (x0, y0), (x1, y1) = origin, target
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    step_x = 1 if x1 > x0 else -1
    step_y = 1 if y1 > y0 else -1
    error = dx - dy
    x, y = x0, y0
    path = []
    for _ in range(dx + dy + 2):
        if (x, y) != origin:
            path.append((x, y))
        if (x, y) == (x1, y1):
            break
        doubled = error * 2
        if doubled > -dy:
            error -= dy
            x += step_x
        if doubled < dx:
            error += dx
            y += step_y
    return path


def bolt_glyph(origin, target) -> str:
    """Which way the bolt is pointing, as one character."""
    dx = (target[0] > origin[0]) - (target[0] < origin[0])
    dy = (target[1] > origin[1]) - (target[1] < origin[1])
    return BOLT_GLYPHS.get((dx, dy), "*")


def clear_shot(world, origin, target) -> bool:
    """Whether a bolt can get from one tile to the other without hitting rock.

    Only walls stop it. Liquids do not: a bolt over a lava pool is fine, and
    treating "cannot walk there" as "cannot shoot over it" would have anything
    with a reach refusing to fire across half the ashfields.

    Being visible is not the same as having a clear line. Field of view is
    generous at the corners by design - it is about what an eye catches - and
    a bolt drawn to something glimpsed past a corner travels through the
    corner. So both are checked, and this is the strict one.
    """
    from world.tiles import Tile

    for coord in trail(origin, target):
        if coord == target:
            return True
        if world.tile_at(*coord) is Tile.WALL:
            return False
    return True


def ready(spell_keys, cooldowns: dict, mana: int | None = None) -> list[Spell]:
    """Which of the creature's spells can be cast this tick, best first.

    Sorted by damage so the agent leads with its heaviest option rather than
    wasting the big one later; a tie goes to the longer reach, since the point
    of casting at all is to not be standing there.
    """
    usable = [
        BY_KEY[key]
        for key in spell_keys
        if key in BY_KEY
        and cooldowns.get(key, 0) <= 0
        and (mana is None or BY_KEY[key].cost <= mana)
    ]
    usable.sort(key=lambda spell: (-spell.damage, -spell.reach))
    return usable


def tick(cooldowns: dict) -> None:
    """Count every cooldown down one tick."""
    for key in list(cooldowns):
        cooldowns[key] -= 1
        if cooldowns[key] <= 0:
            del cooldowns[key]
