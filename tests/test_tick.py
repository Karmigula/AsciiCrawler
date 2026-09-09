import random

from sim.tick import AgentState, tick
from world.hardcoded import Tile, build_map


def _walk(seed: int, steps: int, start: tuple[int, int]) -> list[tuple[int, int]]:
    tiles = build_map(96, 54)
    rng = random.Random(seed)
    agent = AgentState(x=start[0], y=start[1])
    path = []
    for _ in range(steps):
        tick(agent, tiles, rng)
        path.append((agent.x, agent.y))
    return path


def test_tick_moves_exactly_one_cell_orthogonally():
    tiles = build_map(96, 54)
    rng = random.Random(0)
    agent = AgentState(x=48, y=27)
    for _ in range(1000):
        prev = (agent.x, agent.y)
        tick(agent, tiles, rng)
        assert abs(agent.x - prev[0]) + abs(agent.y - prev[1]) == 1


def test_tick_never_enters_a_wall():
    tiles = build_map(96, 54)
    rng = random.Random(99)
    agent = AgentState(x=48, y=27)
    for _ in range(2000):
        tick(agent, tiles, rng)
        assert tiles[agent.y][agent.x] is Tile.FLOOR


def test_tick_is_deterministic_under_a_fixed_seed():
    assert _walk(123, 500, (48, 27)) == _walk(123, 500, (48, 27))


def test_tick_only_uses_passable_neighbors_in_a_corridor():
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR
    rng = random.Random(7)
    agent = AgentState(x=2, y=2)
    for _ in range(200):
        tick(agent, tiles, rng)
        assert agent.y == 2
        assert 1 <= agent.x <= 3


def test_tick_stays_put_when_enclosed_by_walls():
    tiles = [[Tile.WALL] * 3 for _ in range(3)]
    tiles[1][1] = Tile.FLOOR
    agent = AgentState(x=1, y=1)
    tick(agent, tiles, random.Random(3))
    assert (agent.x, agent.y) == (1, 1)
