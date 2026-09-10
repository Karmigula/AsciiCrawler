"""Traps: hidden until spotted or sprung, then remembered and walked around."""

import random
from dataclasses import replace

from agent.memory import Memory
from agent.pathing import astar
from config import DEFAULT_CONFIG
from sim.tick import AgentState, tick
from world.populate import Trap
from world.tiles import Tile

ALWAYS = replace(DEFAULT_CONFIG, trap_detect_chance=1.0)
NEVER = replace(DEFAULT_CONFIG, trap_detect_chance=0.0)


class TrapWorld:
    """Open floor with traps and the lookups the tick asks for."""

    def __init__(self, traps) -> None:
        self.traps = list(traps)

    def tile_at(self, x, y) -> Tile:
        return Tile.FLOOR if 0 <= x < 40 and 0 <= y < 40 else Tile.WALL

    def ensure_loaded(self, position) -> None:
        pass

    def trap_at(self, x, y):
        for trap in self.traps:
            if (trap.x, trap.y) == (x, y):
                return trap
        return None

    def traps_near(self, origin, radius):
        return [
            t
            for t in self.traps
            if max(abs(t.x - origin[0]), abs(t.y - origin[1])) <= radius
        ]


def test_a_trap_in_range_gets_noticed():
    trap = Trap(x=21, y=20)
    agent = AgentState(x=20, y=20)
    tick(agent, TrapWorld([trap]), random.Random(1), ALWAYS)
    assert not trap.hidden
    assert agent.traps_found == 1
    assert agent.memory.believes_hazard((21, 20))


def test_a_trap_out_of_range_is_never_noticed():
    beyond = DEFAULT_CONFIG.trap_detect_radius + 3
    trap = Trap(x=20 + beyond, y=20)
    agent = AgentState(x=20, y=20)
    tick(agent, TrapWorld([trap]), random.Random(1), ALWAYS)
    assert trap.hidden
    assert agent.traps_found == 0


def test_an_unnoticed_trap_stays_hidden():
    trap = Trap(x=21, y=20)
    agent = AgentState(x=20, y=20)
    tick(agent, TrapWorld([trap]), random.Random(1), NEVER)
    assert trap.hidden
    assert not agent.memory.believes_hazard((21, 20))


def test_stepping_in_a_hidden_trap_hurts_and_reveals_it():
    trap = Trap(x=21, y=20)
    agent = AgentState(x=20, y=20)
    agent.explorer.path = [(21, 20)]
    tick(agent, TrapWorld([trap]), random.Random(1), NEVER)
    assert (agent.x, agent.y) == (21, 20)
    assert not trap.hidden
    assert agent.traps_sprung == 1
    assert agent.stats.hp == agent.stats.max_hp - DEFAULT_CONFIG.trap_damage
    assert agent.memory.believes_hazard((21, 20))


def test_a_sprung_trap_does_not_fire_twice():
    trap = Trap(x=21, y=20)
    world = TrapWorld([trap])
    agent = AgentState(x=20, y=20)
    agent.explorer.path = [(21, 20)]
    rng = random.Random(1)
    tick(agent, world, rng, NEVER)
    hurt = agent.stats.hp
    agent.explorer.path = [(20, 20)]
    tick(agent, world, rng, NEVER)
    agent.explorer.path = [(21, 20)]
    tick(agent, world, rng, NEVER)
    assert agent.traps_sprung == 1
    assert agent.stats.hp == hurt


def test_a_known_trap_is_stepped_around_when_there_is_room():
    """Given a detour, the agent takes it."""
    memory = Memory()
    walls = {(x, y): Tile.WALL for x in range(6) for y in (-1, 3)}
    floors = {(x, y): Tile.FLOOR for x in range(6) for y in (0, 1, 2)}
    memory.observe({**walls, **floors}, tick=1)
    memory.mark_hazard((3, 1), tick=1, terrain=Tile.FLOOR)

    path = astar(memory, (0, 1), (5, 1))

    assert path is not None
    assert (3, 1) not in path, "there was a way round"


def test_a_known_trap_in_the_only_doorway_is_walked_through_anyway():
    """The bug this cost: refusing a trapped corridor looks prudent, and walls
    the agent off from everything beyond it. One seed spent 83,000 of 100,000
    ticks with nowhere to go because a single remembered trap sat in a
    one-tile gap - and it never noticed, because it still had a room to
    wander in."""
    memory = Memory()
    walls = {(x, y): Tile.WALL for x in range(6) for y in (0, 2)}
    floors = {(x, 1): Tile.FLOOR for x in range(6)}
    memory.observe({**walls, **floors}, tick=1)
    memory.mark_hazard((3, 1), tick=1, terrain=Tile.FLOOR)

    path = astar(memory, (0, 1), (5, 1))

    assert path is not None, "the only way through is still a way through"
    assert (3, 1) in path


def test_the_agent_can_step_off_a_trap_it_is_standing_on():
    """Only neighbours are filtered — a hazard underfoot must not strand it."""
    memory = Memory()
    memory.observe({(x, 1): Tile.FLOOR for x in range(6)}, tick=1)
    memory.mark_hazard((0, 1), tick=1, terrain=Tile.FLOOR)
    assert astar(memory, (0, 1), (5, 1)) is not None


def test_a_forgotten_trap_can_be_walked_into_again():
    """Decay applies to hard-won knowledge too, which is the point of it."""
    memory = Memory()
    memory.observe({(1, 1): Tile.FLOOR}, tick=1)
    memory.mark_hazard((1, 1), tick=1, terrain=Tile.FLOOR)
    assert memory.believes_hazard((1, 1))
    memory.prune(tick=10_000, ttl=100)
    assert not memory.believes_hazard((1, 1))


def test_knowing_a_trap_survives_looking_at_it_again():
    """Unlike entity snapshots, hazard knowledge is not overwritten by a
    fresh sighting of an apparently empty tile."""
    memory = Memory()
    memory.observe({(1, 1): Tile.FLOOR}, tick=1)
    memory.mark_hazard((1, 1), tick=1, terrain=Tile.FLOOR)
    memory.observe({(1, 1): Tile.FLOOR}, tick=2)
    assert memory.believes_hazard((1, 1))


def test_traps_are_placed_hidden_by_population():
    from world.chunks import ChunkStore

    store = ChunkStore(DEFAULT_CONFIG, world_seed=3)
    traps = [t for cx in range(4) for t in store.get_chunk(cx, 0).contents.traps]
    assert traps
    assert all(t.hidden for t in traps)


def test_a_trap_in_the_only_doorway_does_not_cage_the_agent_forever():
    """A dead-end corridor whose one opening holds a known trap used to pin the
    agent for the rest of the run - and standing still refreshed that trap's
    record every tick, so the knowledge caging it never expired either."""
    from world.tiles import Tile

    class Corridor:
        """Two floor tiles in solid rock: (4,4) and the trapped way out."""

        def tile_at(self, x, y):
            return Tile.FLOOR if (x, y) in {(4, 4), (5, 4)} else Tile.WALL

        def ensure_loaded(self, position):
            pass

        def trap_at(self, x, y):
            return trap if (x, y) == (5, 4) else None

        def traps_near(self, origin, radius):
            return [trap]

    trap = Trap(x=5, y=4)
    world = Corridor()
    agent = AgentState(x=4, y=4)
    rng = random.Random(1)
    tick(agent, world, rng, ALWAYS)  # spots the trap immediately
    assert agent.memory.believes_hazard((5, 4))

    for _ in range(20):
        tick(agent, world, rng, ALWAYS)
        if (agent.x, agent.y) != (4, 4):
            break

    assert (agent.x, agent.y) == (5, 4), "better to take the trap than never move"


def test_a_known_trap_is_still_avoided_when_there_is_another_way():
    """The escape valve must not make the agent careless in open ground."""
    world = TrapWorld([Trap(x=21, y=20, hidden=False)])
    agent = AgentState(x=20, y=20)
    rng = random.Random(1)
    tick(agent, world, rng, ALWAYS)
    assert agent.memory.believes_hazard((21, 20))
    for _ in range(30):
        tick(agent, world, rng, ALWAYS)
        assert (agent.x, agent.y) != (21, 20), "open ground: it should walk around"
