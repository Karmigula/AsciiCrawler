"""Pathing over BELIEVED-passable tiles only — never the world grid.

The belief-vs-truth rule lives here: if memory says a detour is open when
the world says otherwise, the plan produced is confidently wrong, and that
is allowed (stale memory must be able to produce an invalid-looking plan).

Movement model: 8 directions, cardinal step 1.0, diagonal step sqrt(2),
no corner cutting (a diagonal step needs BOTH orthogonal companions
believed passable). Heuristic is octile, consistent with those costs.
Tie-breaking is deterministic: fixed neighbour order plus FIFO insertion.
"""

import heapq
from dataclasses import dataclass
from collections.abc import Iterable, Mapping

from agent.memory import Memory, Position
from world.tiles import Tile

DIRS_8: tuple[tuple[int, int], ...] = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)
_SQRT2 = 2.0**0.5


def _octile(a: Position, b: Position) -> float:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    return max(dx, dy) + (_SQRT2 - 1.0) * min(dx, dy)


@dataclass(frozen=True)
class StepCosts:
    """What a plan pays, on top of distance, to cross awkward ground.

    These live on the config, but a `Memory` does not carry one and the
    pathfinder takes a memory rather than a world. So the tuning travels as a
    value: `from_config` at the call site, defaults everywhere else. Before
    this existed the config fields were decorative - `_neighbors` read its own
    defaults and nothing on the config could change a route.
    """

    hazard: float = 12.0
    ice: float = 2.0
    haze: float = 5.0
    slide_max: int = 0  # 0 models no slide: a step onto ice ends on that ice

    @classmethod
    def from_config(cls, config) -> "StepCosts":
        return cls(
            hazard=config.hazard_step_cost,
            ice=config.ice_step_cost,
            haze=config.haze_step_cost,
            slide_max=config.ice_slide_max if config.model_ice_slides else 0,
        )


DEFAULT_COSTS = StepCosts()


def slide_landing(
    memory: Memory, entry: Position, step: tuple[int, int], slide_max: int
) -> Position:
    """Where a step onto `entry` actually puts the agent, in belief.

    Mirrors `sim.tick._slide`: while the tile underfoot is slippery the agent
    keeps going the way it was already going, up to the cap, stopping at
    anything it cannot enter. Belief is the only input, so ground the agent
    has not seen stops the slide here even where the real floor would carry it
    on - the plan then undershoots, which re-planning fixes, rather than
    overshooting into ground nobody has looked at.

    Monsters are not modelled. Physics stops a slide against a body, so the
    agent sometimes lands short of the prediction; that is a collision, and
    finding out about it by hitting something is the honest way round.
    """
    dx, dy = step
    x, y = entry
    for _ in range(max(0, slide_max)):
        if memory.terrain((x, y)) is not Tile.ICE:
            break
        ahead = (x + dx, y + dy)
        if not memory.believes_passable(ahead):
            break
        x, y = ahead
    return (x, y)


def _neighbors(memory: Memory, pos: Position, costs: StepCosts = DEFAULT_COSTS):
    """Yield (landing, step_cost, crossed) over believed floors, corner-cut safe.

    The yielded coord is where the agent *ends up*, which on ice is not the
    tile it stepped into. Modelling that is what makes frozen ground planable:
    a slide crosses several tiles inside a single tick, so it is fast travel
    that happens to be hard to aim, and a planner that understands it will use
    a frozen hall rather than creep along the rock beside it.

    Cost is charged in ticks, not in tiles - one step is one tick however far
    the ice carries it. `costs.ice` is then charged for *ending* a move on ice,
    which is the part that is actually awkward: the next move from there is at
    the mercy of the same physics.

    `crossed` is the ground a slide passed over on the way. The agent cannot
    stop on any of it, but it does see it go by, which is the whole of what
    exploring a tile means here - so callers that care about coverage rather
    than about standing room get told about it.

    A tile the agent knows is trapped costs `costs.hazard` extra rather than
    being refused. Refusing them looks prudent and is a trap of its own: a
    single remembered trap in a one-tile corridor walls the agent off from
    everything beyond it, and since it still has a whole room to wander in,
    nothing ever notices. One seed spent 83,000 of 100,000 ticks with nowhere
    to go for exactly this reason.

    The cost is a preference rather than a safeguard - a trap the agent has
    spotted is no longer hidden, so walking over it does no damage. It steps
    around when stepping around is cheap, and through when it is not.
    """
    x, y = pos
    for dx, dy in DIRS_8:
        if dx != 0 and dy != 0 and not (
            memory.believes_passable((x + dx, y)) and memory.believes_passable((x, y + dy))
        ):
            continue
        entry = (x + dx, y + dy)
        if not memory.believes_passable(entry):
            continue
        step = _SQRT2 if dx != 0 and dy != 0 else 1.0
        landing = (
            slide_landing(memory, entry, (dx, dy), costs.slide_max)
            if costs.slide_max and memory.terrain(entry) is Tile.ICE
            else entry
        )
        if landing == pos:
            continue  # a slide that returns you where you started is no move
        span = max(abs(landing[0] - x), abs(landing[1] - y))
        crossed = tuple(
            (x + dx * i, y + dy * i) for i in range(1, span)
        )
        if memory.believes_hazard(landing):
            step += costs.hazard
        elif memory.terrain(landing) is Tile.ICE:
            # Ending a move on ice, priced low: enough to prefer bare rock
            # alongside a drift, not enough to refuse a frozen hall that has
            # no way round.
            step += costs.ice
        elif memory.terrain(landing) is Tile.HAZE:
            # Fog is passable and costs hit points, so it is priced like a
            # detour rather than refused: worth crossing to get somewhere,
            # not worth wandering through.
            step += costs.haze
        yield landing, step, crossed


def astar(
    memory: Memory,
    start: Position,
    goal: Position,
    costs: StepCosts = DEFAULT_COSTS,
) -> list[Position] | None:
    """Shortest believed-passable path from start to goal, or None.

    The path lists every step after `start`, ending at `goal`. The search
    graph is finite (memory records only) and the closed set bounds it, so
    unreachable goals terminate; an expansion cap guards against regressions.
    """
    if not memory.believes_passable(start) or not memory.believes_passable(goal):
        return None
    # One tick can cross several tiles on ice, so plain octile distance
    # would overestimate and cost A* its optimality. Divide by the longest
    # a single step can be: weaker guidance, still admissible.
    reach = max(1, costs.slide_max + 1)
    bound = 8 * (len(memory) + 1)  # exceeds the whole graph; pure paranoia
    counter = 0
    open_heap: list[tuple[float, float, int, Position]] = [
        (_octile(start, goal) / reach, 0.0, 0, start)
    ]
    came_from: dict[Position, Position] = {}
    g_score: dict[Position, float] = {start: 0.0}
    closed: set[Position] = set()
    while open_heap:
        _, g, _, pos = heapq.heappop(open_heap)
        if pos in closed:
            continue
        if pos == goal:
            return rebuild_path(came_from, goal, start)
        closed.add(pos)
        if len(closed) > bound:
            return None
        for nxt, step, _crossed in _neighbors(memory, pos, costs):
            tentative = g + step
            if nxt in closed or (nxt in g_score and g_score[nxt] <= tentative):
                continue
            g_score[nxt] = tentative
            came_from[nxt] = pos
            counter += 1
            heapq.heappush(
                open_heap,
                (tentative + _octile(nxt, goal) / reach, tentative, counter, nxt),
            )
    return None


def distances(
    memory: Memory,
    start: Position,
    targets: Iterable[Position] | None = None,
    max_expansions: int | None = None,
    stop_after: int | None = None,
    costs: StepCosts = DEFAULT_COSTS,
) -> tuple[Mapping[Position, float], dict[Position, Position]]:
    """Dijkstra from start over believed floors: (cost-so-far, came-from).

    Absent coords are unreachable in belief. Costs and corner rules match
    `astar`, so each cost equals that coord's A* path length — one sweep
    scores every frontier candidate instead of one search per candidate.

    `targets` bounds the work without changing a single answer. Dijkstra
    settles nodes in nondecreasing cost order, so a node's cost and parent
    are final the moment it closes: once every target has closed there is
    nothing left to learn about them, and the sweep stops. Costs returned
    for those targets are identical to the unbounded sweep's — the caller
    only loses entries for coords it never asked about. Targets that are
    unreachable in belief never close, so the sweep then ends the way it
    always did, by exhausting the reachable component.

    Tiles a slide crosses are reported too, at the cost of the slide that
    passes over them, but only where nothing better reached them. Standing on
    one is impossible; seeing one is not, and a frontier tile stranded in the
    middle of a drift is otherwise unreachable forever - the agent gave up on
    the whole neighbourhood and went back to wandering.

    `stop_after` ends the sweep once that many targets have settled, rather
    than waiting for all of them. The caller only needs a handful of reachable
    candidates to choose between, and Dijkstra settles them nearest first, so
    the ones it gives up on are the far ones that were going to score near
    zero anyway. Without it a single unreachable target in the sample means
    every sweep runs to the expansion cap.

    `None` means sweep everything. A collection means stop once satisfied,
    and the empty collection is satisfied immediately.

    `max_expansions` bounds the work regardless. It is what makes the target
    early-stop dependable: an unreachable target never settles, so without a
    ceiling one such candidate turns every sweep back into a full one over all
    of memory - which is exactly what happened once the agent had remembered
    enough loot it could not reach. Coordinates beyond the cap are reported as
    unreachable, which costs nothing real: score is gain/(1 + cost), so a tile
    thousands of steps away was never going to win.
    """
    if not memory.believes_passable(start):
        return {}, {}
    remaining = None if targets is None else set(targets)
    wanted = len(remaining) if remaining is not None else 0
    settled_targets = 0
    open_heap: list[tuple[float, int, Position]] = [(0.0, 0, start)]
    cost: dict[Position, float] = {start: 0.0}
    came_from: dict[Position, Position] = {}
    closed: set[Position] = set()
    counter = 0
    # Ground a slide crosses is kept to one side until the sweep is over. It
    # cannot be stood on, so it must never be expanded as a node or used to
    # reach anywhere else; it is only ever a place the agent gets a look at.
    passed: dict[Position, float] = {}
    passed_from: dict[Position, Position] = {}
    while open_heap:
        if remaining is not None and not remaining:
            break
        if max_expansions is not None and len(closed) >= max_expansions:
            break
        g, _, pos = heapq.heappop(open_heap)
        if pos in closed:
            continue
        closed.add(pos)
        if remaining is not None and pos in remaining:
            remaining.discard(pos)
            settled_targets += 1
            if stop_after is not None and settled_targets >= stop_after:
                break
        for nxt, step, crossed in _neighbors(memory, pos, costs):
            tentative = g + step
            for tile in crossed:
                if tile not in passed or passed[tile] > tentative:
                    passed[tile] = tentative
                    passed_from[tile] = pos
            if nxt in closed or (nxt in cost and cost[nxt] <= tentative):
                continue
            cost[nxt] = tentative
            came_from[nxt] = pos
            counter += 1
            heapq.heappush(open_heap, (tentative, counter, nxt))
    for tile, value in passed.items():
        if tile not in cost:
            cost[tile] = value
            came_from[tile] = passed_from[tile]
    return cost, came_from


def rebuild_path(came_from: Mapping[Position, Position], goal: Position, start: Position) -> list[Position]:
    """Walk the from-links back from goal; steps after start, goal included.

    Search nodes are landing tiles, so two of them can be a slide apart rather
    than a step apart. The tiles crossed in between are put back here, because
    everything downstream - the physics, the overlay, the sanity check - reads
    a plan as a run of adjacent cells. Slides are straight, so walking the gap
    one cell at a time reproduces exactly the ground the agent will cover.
    """
    if goal == start:
        return []
    path = [goal]
    while path[-1] in came_from and came_from[path[-1]] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return _fill_slides(start, path)


def _fill_slides(start: Position, path: list[Position]) -> list[Position]:
    """Put back the tiles a slide crossed, so every hop in the plan is a step."""
    filled: list[Position] = []
    here = start
    for nxt in path:
        dx, dy = nxt[0] - here[0], nxt[1] - here[1]
        span = max(abs(dx), abs(dy))
        if span > 1:
            ux, uy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
            filled.extend((here[0] + ux * i, here[1] + uy * i) for i in range(1, span))
        filled.append(nxt)
        here = nxt
    return filled
