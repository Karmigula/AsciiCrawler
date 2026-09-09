import random

from config import DEFAULT_CONFIG
from sim.tick import AgentState, tick
from world.tiles import Tile

# ticks to sweep a large open field (measured ~2500 for 96x54; margin on top)
OPEN_FIELD_TICKS = 4000


class FiniteWorld:
    """The old finite-grid world behind the chunk-store interface: tile_at
    answers WALL outside the grid, streaming is a no-op."""

    def __init__(self, tiles: list[list[Tile]]) -> None:
        self.tiles = tiles

    def tile_at(self, x: int, y: int) -> Tile:
        if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[0]):
            return self.tiles[y][x]
        return Tile.WALL

    def ensure_loaded(self, position: tuple[int, int]) -> None:
        pass


def _open_field(width: int = 96, height: int = 54) -> list[list[Tile]]:
    """A FLOOR interior enclosed by a WALL border (open arena for walking)."""
    return [
        [
            Tile.WALL if x in (0, width - 1) or y in (0, height - 1) else Tile.FLOOR
            for x in range(width)
        ]
        for y in range(height)
    ]


def _walk(seed: int, steps: int, start: tuple[int, int]):
    world = FiniteWorld(_open_field())
    rng = random.Random(seed)
    agent = AgentState(x=start[0], y=start[1])
    positions = []
    for _ in range(steps):
        tick(agent, world, rng, DEFAULT_CONFIG)
        positions.append((agent.x, agent.y))
    return agent, positions


def test_tick_moves_at_most_one_cell_per_tick():
    _, positions = _walk(0, 1000, (48, 27))
    previous = (48, 27)
    for current in positions:
        assert max(abs(current[0] - previous[0]), abs(current[1] - previous[1])) <= 1
        previous = current


def test_tick_never_enters_a_wall():
    tiles = _open_field()
    world = FiniteWorld(tiles)
    rng = random.Random(99)
    agent = AgentState(x=48, y=27)
    for _ in range(2000):
        tick(agent, world, rng, DEFAULT_CONFIG)
        assert tiles[agent.y][agent.x] is Tile.FLOOR


def test_tick_is_deterministic_under_a_fixed_seed():
    _, first = _walk(123, 500, (48, 27))
    _, second = _walk(123, 500, (48, 27))
    assert first == second


def test_tick_explores_instead_of_dithering():
    agent, positions = _walk(4, OPEN_FIELD_TICKS, (48, 27))
    assert len(agent.memory) > 3000  # the arena has 5044 tiles
    assert len(set(positions)) > 500


def test_tick_memory_contains_everywhere_the_agent_stood():
    agent, positions = _walk(5, 300, (48, 27))
    for position in positions:
        assert position in agent.memory


def test_tick_only_uses_passable_neighbors_in_a_corridor():
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR
    world = FiniteWorld(tiles)
    rng = random.Random(7)
    agent = AgentState(x=2, y=2)
    for _ in range(200):
        tick(agent, world, rng, DEFAULT_CONFIG)
        assert agent.y == 2
        assert 1 <= agent.x <= 3


def test_tick_stays_put_when_enclosed_by_walls():
    tiles = [[Tile.WALL] * 3 for _ in range(3)]
    tiles[1][1] = Tile.FLOOR
    world = FiniteWorld(tiles)
    agent = AgentState(x=1, y=1)
    for _ in range(100):
        tick(agent, world, random.Random(3), DEFAULT_CONFIG)
        assert (agent.x, agent.y) == (1, 1)


def test_tick_refuses_steps_that_world_truth_rejects():
    """A lied-to memory plans wall steps forever; physics refuses every one.

    Terrain beliefs are never revised (no decay until Phase 3), so the agent
    re-plans through the phantom corridor each tick — and still never enters
    the wall.
    """
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR  # truth: corridor ends at x = 3
    world = FiniteWorld(tiles)
    agent = AgentState(x=3, y=2)
    agent.memory.observe(
        {(x, 2): Tile.FLOOR for x in range(1, 6)}, tick=0
    )  # belief: corridor continues to x = 5
    for _ in range(10):
        tick(agent, world, random.Random(0), DEFAULT_CONFIG)
        assert tiles[agent.y][agent.x] is Tile.FLOOR  # physics never lied to
        assert agent.y == 2 and 1 <= agent.x <= 3  # real corridor only


def test_tick_refuses_to_step_into_liquid():
    """WATER/LAVA are impassable: a believed-passable pond is not entered."""
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR
    tiles[2][3] = Tile.WATER  # truth: the corridor drowns at x = 3
    world = FiniteWorld(tiles)
    agent = AgentState(x=2, y=2)
    agent.memory.observe(
        {(x, 2): Tile.FLOOR for x in range(1, 5)}, tick=0
    )  # belief: dry corridor to x = 4
    for _ in range(20):
        tick(agent, world, random.Random(0), DEFAULT_CONFIG)
        assert (agent.x, agent.y) == (2, 2) or tiles[agent.y][agent.x] is Tile.FLOOR
        assert not (agent.x == 3 and agent.y == 2)  # never stands in the water
