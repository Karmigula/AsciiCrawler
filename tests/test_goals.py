import random

from agent.goals import ExploreGoal, frontier, info_gain
from agent.memory import Memory
from config import DEFAULT_CONFIG
from world.tiles import Tile


def _remember(memory, floors, walls=()):
    observation = {coord: Tile.FLOOR for coord in floors}
    observation.update({coord: Tile.WALL for coord in walls})
    memory.observe(observation, tick=0)


def _room_with_unknown_east_side():
    """A 5x5 floor room, walled on three sides, open (unknown) to the east."""
    memory = Memory()
    floors = {(x, y) for x in range(1, 6) for y in range(1, 6)}
    walls = (
        {(x, 0) for x in range(0, 7)}
        | {(x, 6) for x in range(0, 7)}
        | {(0, y) for y in range(0, 7)}
    )
    _remember(memory, floors, walls)  # column x=6 stays never-seen
    return memory


def test_frontier_is_known_floor_adjacent_to_unknown():
    memory = _room_with_unknown_east_side()
    assert set(frontier(memory)) == {(5, y) for y in range(1, 6)}


def test_frontier_excludes_interior_floor():
    memory = _room_with_unknown_east_side()
    assert (3, 3) not in frontier(memory)


def test_frontier_excludes_known_walls_even_next_to_unknown():
    memory = _room_with_unknown_east_side()
    for wall in frontier(memory):
        assert memory.believes_passable(wall)


def test_frontier_empty_when_everything_around_is_known():
    memory = Memory()
    floors = {(x, y) for x in range(1, 4) for y in range(1, 4)}
    walls = {(x, y) for x in range(0, 5) for y in range(0, 5)} - floors
    _remember(memory, floors, walls)
    assert frontier(memory) == []


def test_info_gain_counts_unknown_neighbours():
    memory = _room_with_unknown_east_side()
    assert info_gain(memory, (5, 3)) == 3  # (6, 2), (6, 3), (6, 4)
    assert info_gain(memory, (3, 3)) == 0


def test_decide_picks_a_reachable_frontier_and_paths_to_it():
    memory = _room_with_unknown_east_side()
    goal = ExploreGoal()
    decision = goal.decide((1, 1), memory, random.Random(7), DEFAULT_CONFIG)
    assert decision is not None
    target, path = decision
    assert target in frontier(memory)
    assert path, "expected a non-empty path"
    assert path[-1] == target
    assert path[0] != (1, 1)
    for step in path:
        assert memory.believes_passable(step)


def test_decide_is_sticky_across_consecutive_decisions():
    memory = _room_with_unknown_east_side()
    goal = ExploreGoal()
    rng = random.Random(21)
    first = goal.decide((1, 1), memory, rng, DEFAULT_CONFIG)
    for _ in range(3):
        again = goal.decide((1, 1), memory, rng, DEFAULT_CONFIG)
    assert again is not None and first is not None
    assert again[0] == first[0], "hysteresis must hold the incumbent target"


def test_decide_yields_when_no_frontier_exists():
    memory = Memory()
    floors = {(x, y) for x in range(1, 4) for y in range(1, 4)}
    walls = {(x, y) for x in range(0, 5) for y in range(0, 5)} - floors
    _remember(memory, floors, walls)
    goal = ExploreGoal()
    assert goal.decide((2, 2), memory, random.Random(0), DEFAULT_CONFIG) is None
    assert goal.path == []
    assert goal.yielded


def test_decide_yields_when_frontier_is_unreachable_in_belief():
    # sealed start chamber (so it holds no frontier of its own) + known but
    # unreachable island whose tiles ARE frontier
    memory = Memory()
    _remember(
        memory,
        floors={(0, 0), (1, 0), (5, 5), (6, 5)},
        walls={
            (-1, -1), (0, -1), (1, -1), (2, -1),
            (-1, 0), (2, 0),
            (-1, 1), (0, 1), (1, 1), (2, 1),
        },
    )
    goal = ExploreGoal()
    assert goal.decide((0, 0), memory, random.Random(0), DEFAULT_CONFIG) is None
    assert goal.yielded


def test_yielded_goal_rethinks_only_when_memory_grows():
    memory = Memory()
    floors = {(x, y) for x in range(1, 4) for y in range(1, 4)}
    walls = {(x, y) for x in range(0, 5) for y in range(0, 5)} - floors
    _remember(memory, floors, walls)
    goal = ExploreGoal()
    goal.decide((2, 2), memory, random.Random(0), DEFAULT_CONFIG)
    assert not goal.wants_rethink(memory, tick=100, throttle_ticks=5)
    memory.observe({(9, 9): Tile.FLOOR}, tick=100)
    assert goal.wants_rethink(memory, tick=100, throttle_ticks=5)


def test_active_plan_rethinks_on_throttle_with_fresh_knowledge():
    memory = _room_with_unknown_east_side()
    goal = ExploreGoal()
    goal.decide((1, 1), memory, random.Random(7), DEFAULT_CONFIG)
    # same knowledge, within throttle: no rethink
    assert not goal.wants_rethink(memory, tick=2, throttle_ticks=5)
    # same knowledge, past throttle: still nothing new to score
    assert not goal.wants_rethink(memory, tick=50, throttle_ticks=5)
    # knowledge grew: rethink
    memory.observe({(9, 9): Tile.FLOOR}, tick=51)
    assert goal.wants_rethink(memory, tick=51, throttle_ticks=5)


def test_exhausted_plan_rethinks_immediately():
    memory = _room_with_unknown_east_side()
    goal = ExploreGoal()
    goal.decide((1, 1), memory, random.Random(7), DEFAULT_CONFIG)
    goal.path = []  # agent arrived: plan exhausted
    assert goal.wants_rethink(memory, tick=1, throttle_ticks=5)


def test_blocked_plan_rethinks_immediately():
    memory = _room_with_unknown_east_side()
    goal = ExploreGoal()
    goal.decide((1, 1), memory, random.Random(7), DEFAULT_CONFIG)
    goal.drop_plan()  # physics refused a step
    assert goal.wants_rethink(memory, tick=1, throttle_ticks=5)
