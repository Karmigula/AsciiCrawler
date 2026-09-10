"""Bump combat: walking into something is how you hit it, in both directions.

There is no attack command and no turn menu — this is an aquarium, and the
agent's intent to fight is expressed by its feet. A step into an occupied tile
becomes a blow and the step is spent.

Damage is `attack - defense`, floored at 1 so that nothing is ever completely
immune to anything, plus a seeded 0..damage_variance roll. Monsters have no
defense stat (their tier already prices them), so the floor rarely binds for
the agent and frequently binds for a rat swinging at armour.

Both sides of a blow read the agent's *derived* numbers, never the bare Stats.
That is the whole point of the loadout bundle: reading `stats.attack` here
would mean a cruel sword raised the number on the HUD, satisfied the loadout
evaluator, and changed nothing about how hard the agent actually hits.
"""

import random

from config import Config


def roll_damage(attack: int, defense: int, rng: random.Random, config: Config) -> int:
    """One blow's damage: at least 1, plus a seeded variance roll."""
    return max(1, attack - defense) + rng.randint(0, config.damage_variance)


def agent_hits_monster(derived, monster, rng: random.Random, config: Config) -> int:
    """Resolve the agent's blow with its effective attack. Returns damage dealt."""
    damage = roll_damage(derived.attack, 0, rng, config)
    monster.hp -= damage
    return damage


def monster_hits_agent(
    monster, stats, derived, rng: random.Random, config: Config
) -> int:
    """Resolve a monster's blow against effective defense. Returns damage landed.

    `stats` still takes the wound - hit points live on the body - but the
    mitigation comes from `derived`, so worn armour actually blunts the blow.
    """
    return stats.take(roll_damage(monster.kind.attack, derived.defense, rng, config))


def xp_for(monster, config: Config) -> int:
    """What a corpse is worth — deeper tiers pay more."""
    return (monster.kind.tier + 1) * config.xp_per_tier
