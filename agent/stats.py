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
    # Mana. Spent to cast, refilled slowly, and refilled outright on a level
    # the way hit points are - a promotion should feel like one.
    mp: int = 0
    max_mp: int = 0
    level: int = 1
    xp: int = 0

    @classmethod
    def starting(cls, config: Config) -> "Stats":
        return cls(
            hp=config.agent_max_hp,
            max_hp=config.agent_max_hp,
            attack=config.agent_attack,
            defense=config.agent_defense,
            mp=config.agent_max_mp,
            max_mp=config.agent_max_mp,
        )

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take(self, damage: int) -> int:
        """Apply damage (never healing), return what actually landed."""
        damage = max(0, damage)
        self.hp -= damage
        return damage

    def spend(self, amount: int) -> bool:
        """Pay for a spell if there is mana for it. True if it was paid.

        Asking and paying in one place: a caller that checks first and spends
        later is a caller that eventually forgets to do one of them.
        """
        if amount <= 0:
            return True
        if self.mp < amount:
            return False
        self.mp -= amount
        return True

    def recover(self, amount: int, ceiling: int | None = None) -> None:
        """Trickle mana back, never past the maximum gear allows."""
        top = self.max_mp if ceiling is None else max(self.max_mp, ceiling)
        self.mp = min(top, self.mp + max(0, amount))

    def xp_to_next(self, config: Config) -> int:
        """Total xp required to reach the level after this one."""
        return round(config.xp_level_base * config.xp_level_growth ** (self.level - 1))

    def gain_xp(self, amount: int, config: Config, ceiling: int | None = None) -> int:
        """Bank xp and level up as many times as it pays for. Returns levels gained.

        Levelling heals to the new maximum: it is the only healing in the game,
        which makes a level-up the thing that saves the agent's life rather
        than merely a bigger number.

        `ceiling` is the *effective* maximum once gear is folded in, which is
        higher than `max_hp` whenever a +max_hp affix is worn. Without it a
        level-up would heal to the bare-body maximum and so take hit points
        away from an agent in good armour - a promotion that wounds you.
        """
        self.xp += max(0, amount)
        levels = 0
        while self.xp >= self.xp_to_next(config):
            self.xp -= self.xp_to_next(config)
            self.level += 1
            self.max_hp += config.level_hp_gain
            self.max_mp += config.level_mp_gain
            self.mp = self.max_mp
            self.attack += config.level_attack_gain
            self.hp = max(self.hp, self.max_hp if ceiling is None else max(self.max_hp, ceiling))
            levels += 1
        return levels
