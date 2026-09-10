"""One world, ticking, with the bookkeeping a long-running host needs.

The desktop loop owns its world directly and can afford to: someone is
watching it, and when they close the window everything goes away. A server
runs for weeks, so this adds the two things that only matter over time -
lives get written to the hall as they end, and the world is rotated before it
grows without bound.

Nothing here draws anything or knows what is watching.
"""

import random

from config import DEFAULT_CONFIG, Config
from sim import hall
from sim.tick import AgentState, tick
from world.chunks import ChunkStore


def should_restart(config: Config, deaths: int, deaths_seen: int) -> bool:
    """Whether a death should end this world and roll the next one.

    Pulled out of the loop so the rule can be tested: the loop itself needs a
    window, and this is the part with an actual decision in it.
    """
    return config.new_world_on_death and deaths > deaths_seen


class Session:
    """A world, the creature in it, and the rules for starting another.

    `max_ticks` rotates the world even when the agent refuses to die. Chunks
    are never discarded once streamed, which is the right call for a desktop
    toy someone closes at bedtime and a slow leak for a server that stays up
    for a month. Rotating also keeps the tank worth watching: a fresh seed is
    a different set of biomes.
    """

    def __init__(
        self,
        config: Config = DEFAULT_CONFIG,
        seed: int | None = None,
        max_ticks: int = 0,
        record_hall: bool = True,
    ) -> None:
        self.config = config
        self.seed = config.world_seed if seed is None else seed
        self.max_ticks = max_ticks
        self.record_hall = record_hall
        self.worlds = 0
        self._deaths_seen = 0
        self._start()

    def _start(self) -> None:
        self.world = ChunkStore(self.config, world_seed=self.seed)
        spawn = self.world.spawn
        self.agent = AgentState(x=spawn[0], y=spawn[1])
        self.rng = random.Random(self.seed + 1)
        self._deaths_seen = 0
        self.worlds += 1

    def _next_world(self) -> None:
        self.seed += 1
        self._start()

    def advance(self, steps: int = 1) -> None:
        """Tick the world on, recording lives and rolling worlds as needed."""
        for _ in range(max(0, steps)):
            tick(self.agent, self.world, self.rng, self.config)
            while self.agent.fallen:
                # The tick records lives; writing them down is this loop's
                # job, which keeps sim/tick.py free of file handling.
                fallen = self.agent.fallen.pop(0)
                if self.record_hall:
                    hall.remember(fallen)
            if should_restart(self.config, self.agent.deaths, self._deaths_seen):
                self._next_world()
                continue
            self._deaths_seen = self.agent.deaths
            if self.max_ticks and self.agent.tick_count >= self.max_ticks:
                self._next_world()
