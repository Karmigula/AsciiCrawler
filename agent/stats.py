"""The agent's body: hit points, offence, and the experience it has earned.

Kept apart from `AgentState` (which is about position, memory and plans) and
apart from the Phase 5 loadout, which will *modify* these numbers rather than
replace them. Nothing here reads the world; damage is applied from outside.

Death resets stats but never memory. That is the aquarium's central bargain:
the creature you are watching dies and starts over weak, but it still knows
where it has been, so it does not re-run the same first ten minutes forever.
"""

from dataclasses import dataclass

from config import Config


@dataclass
class Stats:
    """Hit points and growth. `level` starts at 1; `xp` is the running total."""

    hp: int
    max_hp: int
    attack: int
    defense: int
    level: int = 1
    xp: int = 0

    @classmethod
    def starting(cls, config: Config) -> "Stats":
        return cls(
            hp=config.agent_max_hp,
            max_hp=config.agent_max_hp,
            attack=config.agent_attack,
            defense=config.agent_defense,
        )

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take(self, damage: int) -> int:
        """Apply damage (never healing), return what actually landed."""
        damage = max(0, damage)
        self.hp -= damage
        return damage

    def xp_to_next(self, config: Config) -> int:
        """Total xp required to reach the level after this one."""
        return round(config.xp_level_base * config.xp_level_growth ** (self.level - 1))

    def gain_xp(self, amount: int, config: Config) -> int:
        """Bank xp and level up as many times as it pays for. Returns levels gained.

        Levelling heals to the new maximum: it is the only healing in the game
        this phase, which makes a level-up the thing that saves the agent's
        life rather than merely a bigger number.
        """
        self.xp += max(0, amount)
        levels = 0
        while self.xp >= self.xp_to_next(config):
            self.xp -= self.xp_to_next(config)
            self.level += 1
            self.max_hp += config.level_hp_gain
            self.attack += config.level_attack_gain
            self.hp = self.max_hp
            levels += 1
        return levels
