import pytest

from agent.memory import Memory
from agent.pathing import astar, distances, rebuild_path
from world.tiles import Tile


def _memory_of(floors, walls=()):
    memory = Memory()
    observation = {coord: Tile.FLOOR for coord in floors}
    observation.update({coord: Tile.WALL for coord in walls})
    memory.observe(observation, tick=0)
    return memory


def _open_grid(width, height):
    return _memory_of(
        {(x, y) for x in range(width) for y in range(height)},
        walls={(x, -1) for x in range(-1, width + 1)}
        | {(x, height) for x in range(-1, width + 1)}
        | {(-1, y) for y in range(-1, height + 1)}
        | {(width, y) for y in range(-1, height + 1)},
    )


def _assert_sane(path, start, goal):
    assert path, "path must be non-empty"
    assert path[0] != start, "path must not include the start"
    assert path[-1] == goal
    previous = start
    for step in path:
        assert max(abs(step[0] - previous[0]), abs(step[1] - previous[1])) == 1
        previous = step


def test_astar_open_grid_path_is_optimal():
    memory = _open_grid(10, 10)
    path = astar(memory, (0, 0), (7, 5))
    assert path is not None
    _assert_sane(path, (0, 0), (7, 5))
    assert len(path) == 7  # chebyshev distance: 7 steps, 5 of them diagonal
    for step in path:
        assert memory.believes_passable(step)


def test_astar_adjacent_goal_is_single_step():
    memory = _open_grid(3, 3)
    assert astar(memory, (1, 1), (2, 1)) == [(2, 1)]


def test_astar_walls_force_a_detour_through_the_gap():
    floors = {(x, y) for x in range(7) for y in range(5)}
    walls = {(3, y) for y in range(4)}  # wall column, gap only at (3, 4)
    memory = _memory_of(floors, walls)
    path = astar(memory, (0, 0), (6, 0))
    assert path is not None
    _assert_sane(path, (0, 0), (6, 0))
    assert (3, 4) in path
    # the gap tile must be entered orthogonally (its diagonal companions are
    # walls), so the true optimum is 5 steps down + 5 back up
    assert len(path) == 10


def test_astar_unreachable_goal_returns_none():
    floors = {(x, y) for x in range(7) for y in range(5)}
    walls = {(3, y) for y in range(5)}  # solid wall column: no gap at all
    memory = _memory_of(floors, walls)
    assert astar(memory, (0, 0), (6, 0)) is None


def test_astar_never_paths_through_unknown_tiles():
    # L-shaped known corridor; the diagonal shortcut (1, 1) is never-seen
    corridor = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (2, 3), (2, 4)]
    memory = _memory_of(corridor)
    path = astar(memory, (0, 0), (2, 4))
    assert path is not None
    _assert_sane(path, (0, 0), (2, 4))
    assert len(path) == 6  # the L, not the (blocked) diagonal
    assert (1, 1) not in path
    for step in path:
        assert step in memory


def test_astar_never_paths_through_believed_walls():
    floors = {(0, 0), (1, 1), (2, 2)}
    walls = {(1, 0), (0, 1)}  # both orthogonal companions of the diagonal
    memory = _memory_of(floors, walls)
    assert astar(memory, (0, 0), (1, 1)) is None  # corner cutting refused


def test_astar_returns_none_for_unknown_endpoints():
    memory = _memory_of({(0, 0), (1, 0)})
    assert astar(memory, (0, 0), (5, 5)) is None
    assert astar(memory, (9, 9), (0, 0)) is None


def test_astar_is_deterministic():
    memory = _open_grid(12, 9)
    assert astar(memory, (1, 1), (10, 7)) == astar(memory, (1, 1), (10, 7))


def _blob_memory(width: int = 40, height: int = 30, walls=()) -> Memory:
    """An open believed-floor rectangle, minus any walls named by the caller."""
    memory = Memory()
    memory.observe(
        {
            (x, y): (Tile.WALL if (x, y) in set(walls) else Tile.FLOOR)
            for y in range(height)
            for x in range(width)
        },
        tick=0,
    )
    return memory


def test_targeted_distances_match_the_full_sweep_exactly():
    """Early termination is an optimisation, not a behaviour change.

    Dijkstra settles nodes in nondecreasing cost order, so a node's cost is
    final the moment it closes; stopping once every target has closed must
    give byte-identical costs for those targets.
    """
    walls = [(10, y) for y in range(0, 25)] + [(25, y) for y in range(5, 30)]
    memory = _blob_memory(walls=walls)
    start = (2, 2)
    targets = [(5, 5), (12, 20), (30, 28), (39, 0), (8, 15)]
    full_cost, full_from = distances(memory, start)
    part_cost, part_from = distances(memory, start, targets=targets)
    for target in targets:
        assert part_cost.get(target) == full_cost.get(target)
        assert rebuild_path(part_from, target, start) == rebuild_path(
            full_from, target, start
        )


def test_targeted_distances_agree_with_astar_path_length():
    """The claim goals.py relies on: a sweep cost IS that coord's A* length."""
    walls = [(10, y) for y in range(0, 25)]
    memory = _blob_memory(walls=walls)
    start = (2, 2)
    for target in ((5, 5), (12, 20), (30, 28), (20, 3)):
        path = astar(memory, start, target)
        cost, _ = distances(memory, start, targets=[target])
        assert path is not None
        expected = 0.0
        cursor = start
        for step in path:
            diagonal = step[0] != cursor[0] and step[1] != cursor[1]
            expected += 2.0**0.5 if diagonal else 1.0
            cursor = step
        assert cost[target] == pytest.approx(expected)


def test_targeting_an_unreachable_coord_still_terminates():
    """A sealed-off target cannot settle, so the sweep must end by exhaustion."""
    walls = [(10, y) for y in range(30)]
    memory = _blob_memory(walls=walls)
    cost, _ = distances(memory, (2, 2), targets=[(20, 20), (5, 5)])
    assert cost.get((20, 20)) is None  # walled off
    assert cost.get((5, 5)) is not None


def test_a_targeted_sweep_settles_fewer_nodes_than_the_full_one():
    """The point of the exercise: less work, same answers."""
    memory = _blob_memory()
    full_cost, _ = distances(memory, (2, 2))
    part_cost, _ = distances(memory, (2, 2), targets=[(4, 4)])
    assert len(part_cost) < len(full_cost)
    assert part_cost[(4, 4)] == full_cost[(4, 4)]


def test_the_two_target_modes_are_distinct():
    """None means sweep everything; a collection means stop once it is
    satisfied — and the empty collection is satisfied immediately."""
    memory = _blob_memory()
    full_cost, _ = distances(memory, (2, 2))
    empty_cost, _ = distances(memory, (2, 2), targets=[])
    assert len(full_cost) > 100
    assert list(empty_cost) == [(2, 2)]  # start only: nothing to wait for


def test_the_expansion_cap_bounds_a_sweep_that_cannot_finish():
    """An unreachable target never settles, so without a ceiling one candidate
    turns every sweep into a full one over all of memory."""
    memory = _blob_memory(60, 60)
    walled_off = (100, 100)  # outside the blob entirely
    uncapped, _ = distances(memory, (2, 2), targets=[walled_off])
    capped, _ = distances(memory, (2, 2), targets=[walled_off], max_expansions=200)
    assert len(uncapped) > 2000, "setup: the uncapped sweep should exhaust the blob"
    assert len(capped) <= 250
    assert capped.get(walled_off) is None


def test_the_cap_does_not_disturb_a_target_it_reaches_first():
    memory = _blob_memory(60, 60)
    near = (5, 5)
    full, _ = distances(memory, (2, 2), targets=[near])
    capped, _ = distances(memory, (2, 2), targets=[near], max_expansions=3000)
    assert capped[near] == full[near]


def test_a_target_past_the_cap_reads_as_unreachable():
    memory = _blob_memory(60, 60)
    far = (58, 58)
    reachable, _ = distances(memory, (2, 2), targets=[far])
    assert reachable.get(far) is not None
    capped, _ = distances(memory, (2, 2), targets=[far], max_expansions=50)
    assert capped.get(far) is None


def test_step_costs_are_read_from_the_config_not_from_defaults():
    """A config knob that no route can feel is a knob that does not exist.

    `haze_step_cost` shipped dead for exactly this reason: the field was on
    the config, `_neighbors` had a parameter for it, and nothing connected the
    two - so every route in the game was planned with the module defaults. The
    test pins the wiring rather than the number: raise the price of fog high
    enough and the plan must go round it.
    """
    from dataclasses import replace

    from agent.pathing import StepCosts, astar
    from config import DEFAULT_CONFIG

    # A short fogged corridor between the ends, and a long clean way round.
    memory = Memory()
    seen = {}
    for x in range(1, 6):
        seen[(x, 0)] = Tile.HAZE  # the direct route: five tiles of fog
    for x in range(7):
        seen[(x, 4)] = Tile.FLOOR  # the long way, four rows south
    for y in range(5):
        seen[(0, y)] = Tile.FLOOR
        seen[(6, y)] = Tile.FLOOR
    memory.observe(seen, tick=0)

    cheap = StepCosts.from_config(replace(DEFAULT_CONFIG, haze_step_cost=0.0))
    dear = StepCosts.from_config(replace(DEFAULT_CONFIG, haze_step_cost=50.0))

    through = astar(memory, (0, 0), (6, 0), costs=cheap)
    around = astar(memory, (0, 0), (6, 0), costs=dear)
    assert through is not None and around is not None
    assert any(memory.terrain(step) is Tile.HAZE for step in through)
    assert not any(memory.terrain(step) is Tile.HAZE for step in around)


def test_the_goal_layer_hands_the_configs_step_costs_to_the_pathfinder():
    """The wiring bug lived in the goal layer, so the test lives there too.

    The sibling test above proves `astar` honours the costs it is handed -
    which is exactly what the shipped-dead `haze_step_cost` also did. What was
    missing was anyone handing them over, so this pins the handover itself:
    every sweep the goal layer starts must carry the costs the config asked
    for, not the module defaults.
    """
    import random
    from dataclasses import replace

    import agent.goals as goals
    from agent.pathing import StepCosts
    from config import DEFAULT_CONFIG

    config = replace(
        DEFAULT_CONFIG, hazard_step_cost=3.0, ice_step_cost=7.0, haze_step_cost=9.0
    )
    seen: list = []
    real = goals.distances

    def spy(*args, **kwargs):
        seen.append(kwargs.get("costs"))
        return real(*args, **kwargs)

    memory = Memory()
    memory.observe({(x, y): Tile.FLOOR for x in range(5) for y in range(5)}, tick=0)

    goals.distances = spy
    try:
        goals.ExploreGoal().decide((2, 2), memory, random.Random(1), config)
        goals.LootGoal().decide((2, 2), memory, {}, config)
    finally:
        goals.distances = real

    assert seen, "the goal layer never ran a sweep; the test proves nothing"
    assert all(c == StepCosts.from_config(config) for c in seen), (
        f"a sweep planned on defaults instead of the config: {seen}"
    )
