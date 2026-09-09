from agent.memory import Memory
from agent.pathing import astar
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
