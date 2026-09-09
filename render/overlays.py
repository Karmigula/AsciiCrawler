"""Debug overlays: tinting the glyph grid to show what the agent is thinking.

Each overlay takes the drawable grid the fog produced and returns a new grid
with colours replaced. They are diagnostic instruments, so they show belief
rather than truth wherever the two differ - an overlay that quietly consulted
the world would be useless for the one job it has, which is answering "why is
it doing that?"

Pygame-free and pure: an overlay is a grid in, a grid out.
"""

from agent.threat import danger

Color = tuple[int, int, int]
Cell = tuple[str, Color] | None
Grid = list[list[Cell]]

FOV = "fov"
AGE = "age"
THREAT = "threat"
PLAN = "plan"
FRONTIER = "frontier"

OVERLAY_NAMES = (FOV, AGE, THREAT, PLAN, FRONTIER)


def _blend(a: Color, b: Color, weight: float) -> Color:
    weight = max(0.0, min(1.0, weight))
    return (
        round(a[0] + (b[0] - a[0]) * weight),
        round(a[1] + (b[1] - a[1]) * weight),
        round(a[2] + (b[2] - a[2]) * weight),
    )


def apply_overlay(
    grid: Grid,
    name: str,
    origin: tuple[int, int],
    agent,
    visible: set,
    config,
) -> Grid:
    """Return a recoloured copy of `grid` for the named overlay."""
    if name == FOV:
        return _tint_set(grid, origin, visible, config.overlay_hot_color)
    if name == AGE:
        return _tint_age(grid, origin, agent, config)
    if name == THREAT:
        return _tint_threat(grid, origin, agent, config)
    if name == PLAN:
        return _tint_plan(grid, origin, agent, config)
    if name == FRONTIER:
        return _tint_frontier(grid, origin, agent, config)
    return grid


def _tint_set(grid: Grid, origin, coords, color: Color) -> Grid:
    ox, oy = origin
    return [
        [
            (cell[0], color) if cell is not None and (x + ox, y + oy) in coords else cell
            for x, cell in enumerate(row)
        ]
        for y, row in enumerate(grid)
    ]


def _tint_age(grid: Grid, origin, agent, config) -> Grid:
    """Fresh memory hot, stale memory cold - the decay gradient made visible."""
    ox, oy = origin
    ttl = agent.derived.memory_ttl if agent.derived else config.memory_ttl
    out: Grid = []
    for y, row in enumerate(grid):
        line: list[Cell] = []
        for x, cell in enumerate(row):
            coord = (x + ox, y + oy)
            if cell is None or coord not in agent.memory:
                line.append(cell)
                continue
            age = agent.memory.age(coord, agent.tick_count)
            line.append(
                (
                    cell[0],
                    _blend(
                        config.overlay_hot_color,
                        config.overlay_cold_color,
                        min(1.0, age / max(1, ttl)),
                    ),
                )
            )
        out.append(line)
    return out


def _tint_threat(grid: Grid, origin, agent, config) -> Grid:
    """How frightening the agent believes each tile to be.

    Sampled only for tiles memory holds, and only near remembered monsters, so
    the cost stays with what is on screen.
    """
    ox, oy = origin
    ceiling = max(0.1, config.flee_threat)
    out: Grid = []
    for y, row in enumerate(grid):
        line: list[Cell] = []
        for x, cell in enumerate(row):
            coord = (x + ox, y + oy)
            if cell is None or coord not in agent.memory:
                line.append(cell)
                continue
            level = danger(agent.memory, coord, config)
            if level <= 0:
                line.append(cell)
                continue
            line.append(
                (
                    cell[0],
                    _blend(
                        config.overlay_cold_color,
                        config.overlay_danger_color,
                        level / ceiling,
                    ),
                )
            )
        out.append(line)
    return out


def _tint_plan(grid: Grid, origin, agent, config) -> Grid:
    """The route the agent intends to walk, and what it is aiming at."""
    driver = _driver(agent)
    path = set(driver.path)
    grid = _tint_set(grid, origin, path, config.overlay_plan_color)
    target = getattr(driver, "target", None)
    if target is not None:
        grid = _tint_set(grid, origin, {target}, config.overlay_hot_color)
    return grid


def _tint_frontier(grid: Grid, origin, agent, config) -> Grid:
    """Everywhere the agent believes it could still learn something."""
    from agent.goals import frontier

    return _tint_set(grid, origin, set(frontier(agent.memory)), config.overlay_plan_color)


def _driver(agent):
    """Whichever goal currently holds the wheel."""
    if agent.fleer.active:
        return agent.fleer
    if agent.looter.path:
        return agent.looter
    return agent.explorer
