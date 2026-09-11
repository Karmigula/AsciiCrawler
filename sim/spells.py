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
    """

    key: str
    label: str
    reach: int
    damage: int
    cooldown: int
    inflicts: str = ""


SPELLS: tuple[Spell, ...] = (
    Spell("ember_bolt", "ember bolt", reach=6, damage=7, cooldown=18),
    Spell("frost_lance", "frost lance", reach=5, damage=4, cooldown=14, inflicts="chilled"),
    Spell("withering", "withering", reach=5, damage=3, cooldown=20, inflicts="withered"),
    Spell("spark", "spark", reach=4, damage=3, cooldown=10),
)

BY_KEY = {spell.key: spell for spell in SPELLS}


def ready(spell_keys, cooldowns: dict) -> list[Spell]:
    """Which of the creature's spells can be cast this tick, best first.

    Sorted by damage so the agent leads with its heaviest option rather than
    wasting the big one later; a tie goes to the longer reach, since the point
    of casting at all is to not be standing there.
    """
    usable = [
        BY_KEY[key]
        for key in spell_keys
        if key in BY_KEY and cooldowns.get(key, 0) <= 0
    ]
    usable.sort(key=lambda spell: (-spell.damage, -spell.reach))
    return usable


def tick(cooldowns: dict) -> None:
    """Count every cooldown down one tick."""
    for key in list(cooldowns):
        cooldowns[key] -= 1
        if cooldowns[key] <= 0:
            del cooldowns[key]
