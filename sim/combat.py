"""Bump combat: walking into something is how you hit it, in both directions.

There is no attack command and no turn menu — this is an aquarium, and the
agent's intent to fight is expressed by its feet. A step into an occupied tile
becomes a blow and the step is spent.

Damage is `attack - defense`, floored at 1 so that nothing is ever completely
immune to anything, plus a seeded 0..damage_variance roll. Monsters have no
defense stat (their tier already prices them), so the floor rarely binds for
the agent and frequently binds for a rat swinging at armour.
"""

import random

from config import Config


def roll_damage(attack: int, defense: int, rng: random.Random, config: Config) -> int:
    """One blow's damage: at least 1, plus a seeded variance roll."""
    return max(1, attack - defense) + rng.randint(0, config.damage_variance)


def agent_hits_monster(stats, monster, rng: random.Random, config: Config) -> int:
    """Resolve the agent's blow. Returns the damage dealt."""
    damage = roll_damage(stats.attack, 0, rng, config)
    monster.hp -= damage
    return damage


def monster_hits_agent(monster, stats, rng: random.Random, config: Config) -> int:
    """Resolve a monster's blow. Returns the damage that landed."""
    return stats.take(roll_damage(monster.kind.attack, stats.defense, rng, config))


def xp_for(monster, config: Config) -> int:
    """What a corpse is worth — deeper tiers pay more."""
    return (monster.kind.tier + 1) * config.xp_per_tier
