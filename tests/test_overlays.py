"""Debug overlays: recolouring the grid to show what the agent believes."""

import random

from config import DEFAULT_CONFIG
from render.overlays import AGE, FOV, FRONTIER, OVERLAY_NAMES, PLAN, THREAT, apply_overlay
from sim.tick import AgentState, tick
from world.tiles import Tile

WHITE = (200, 200, 200)


class OpenWorld:
    def tile_at(self, x, y):
        return Tile.FLOOR if abs(x) < 40 and abs(y) < 40 else Tile.WALL

    def ensure_loaded(self, position):
        pass


def _agent(ticks: int = 4) -> AgentState:
    agent = AgentState(x=0, y=0)
    rng = random.Random(1)
    for _ in range(ticks):
        tick(agent, OpenWorld(), rng, DEFAULT_CONFIG)
    return agent


def _grid(width: int = 9, height: int = 9):
    return [[(".", WHITE) for _ in range(width)] for _ in range(height)]


def _origin(agent, size: int = 9):
    return (agent.x - size // 2, agent.y - size // 2)


def _colors(grid):
    return {cell[1] for row in grid for cell in row if cell is not None}


def test_every_named_overlay_returns_a_grid_of_the_same_shape():
    agent = _agent()
    grid = _grid()
    for name in OVERLAY_NAMES:
        out = apply_overlay(grid, name, _origin(agent), agent, {(0, 0)}, DEFAULT_CONFIG)
        assert len(out) == len(grid)
        assert all(len(a) == len(b) for a, b in zip(out, grid))


def test_an_overlay_does_not_scribble_on_the_grid_it_was_given():
    agent = _agent()
    grid = _grid()
    before = [row[:] for row in grid]
    apply_overlay(grid, FOV, _origin(agent), agent, {(0, 0)}, DEFAULT_CONFIG)
    assert grid == before


def test_an_unknown_overlay_changes_nothing():
    agent = _agent()
    grid = _grid()
    assert apply_overlay(grid, "nonsense", _origin(agent), agent, set(), DEFAULT_CONFIG) == grid


def test_the_fov_overlay_marks_exactly_what_is_visible():
    agent = _agent()
    origin = _origin(agent)
    visible = {(agent.x, agent.y), (agent.x + 1, agent.y)}
    out = apply_overlay(_grid(), FOV, origin, agent, visible, DEFAULT_CONFIG)
    hot = DEFAULT_CONFIG.overlay_hot_color
    marked = {
        (x + origin[0], y + origin[1])
        for y, row in enumerate(out)
        for x, cell in enumerate(row)
        if cell[1] == hot
    }
    assert marked == visible


def test_the_age_overlay_makes_a_gradient_out_of_decay():
    """Tiles seen at different times must shade differently - one age is one
    colour, which is correct but proves nothing."""
    agent = _agent()
    agent.memory.observe({(agent.x + 1, agent.y): Tile.FLOOR}, tick=1)
    agent.memory.observe(
        {(agent.x + 2, agent.y): Tile.FLOOR}, tick=DEFAULT_CONFIG.memory_ttl // 2
    )
    agent.tick_count = DEFAULT_CONFIG.memory_ttl
    origin = _origin(agent)
    out = apply_overlay(_grid(), AGE, origin, agent, set(), DEFAULT_CONFIG)

    def shade(coord):
        return out[coord[1] - origin[1]][coord[0] - origin[0]][1]

    def distance_from_hot(color):
        hot = DEFAULT_CONFIG.overlay_hot_color
        return sum((a - b) ** 2 for a, b in zip(color, hot))

    fresher = shade((agent.x + 2, agent.y))  # seen at ttl/2
    older = shade((agent.x + 1, agent.y))  # seen at tick 1
    assert distance_from_hot(fresher) < distance_from_hot(older)
    assert len(_colors(out)) >= 2


def test_the_threat_overlay_lights_up_near_a_remembered_monster():
    agent = _agent()
    agent.memory.observe(
        {(agent.x + 2, agent.y): Tile.FLOOR},
        tick=agent.tick_count,
        entities={(agent.x + 2, agent.y): "D"},
    )
    plain = apply_overlay(_grid(), THREAT, _origin(agent), agent, set(), DEFAULT_CONFIG)
    assert DEFAULT_CONFIG.overlay_danger_color[0] > 0
    assert len(_colors(plain)) > 1, "a remembered dragon should tint its surroundings"


def test_the_threat_overlay_stays_quiet_when_nothing_is_remembered():
    agent = _agent()
    out = apply_overlay(_grid(), THREAT, _origin(agent), agent, set(), DEFAULT_CONFIG)
    assert _colors(out) == {WHITE}


def test_the_plan_overlay_draws_the_route_and_the_target():
    agent = _agent()
    agent.explorer.path = [(agent.x + 1, agent.y), (agent.x + 2, agent.y)]
    agent.explorer.target = (agent.x + 2, agent.y)
    agent.fleer.active = False
    agent.looter.clear()
    out = apply_overlay(_grid(), PLAN, _origin(agent), agent, set(), DEFAULT_CONFIG)
    assert DEFAULT_CONFIG.overlay_plan_color in _colors(out)
    assert DEFAULT_CONFIG.overlay_hot_color in _colors(out)


def test_the_frontier_overlay_marks_somewhere_to_go():
    """The window has to be wide enough to contain the frontier: it sits at
    the edge of what has been seen, not next to the agent."""
    agent = _agent()
    size = 2 * DEFAULT_CONFIG.fov_radius + 5
    out = apply_overlay(
        _grid(size, size), FRONTIER, _origin(agent, size), agent, set(), DEFAULT_CONFIG
    )
    assert DEFAULT_CONFIG.overlay_plan_color in _colors(out)


def test_overlays_leave_blank_cells_blank():
    """Unknown ground stays unknown: an overlay must not reveal the map."""
    agent = _agent()
    grid = _grid()
    grid[0][0] = None
    out = apply_overlay(grid, FOV, _origin(agent), agent, {(agent.x, agent.y)}, DEFAULT_CONFIG)
    assert out[0][0] is None
