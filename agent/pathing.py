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
from collections.abc import Iterable, Mapping

from agent.memory import Memory, Position

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


def _neighbors(memory: Memory, pos: Position, hazard_cost: float = 12.0):
    """Yield (neighbor, step_cost) over believed floors, corner-cut safe.

    A tile the agent knows is trapped costs `hazard_cost` extra rather than
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
        nxt = (x + dx, y + dy)
        if not memory.believes_passable(nxt):
            continue
        step = _SQRT2 if dx != 0 and dy != 0 else 1.0
        if memory.believes_hazard(nxt):
            step += hazard_cost
        yield nxt, step


def astar(memory: Memory, start: Position, goal: Position) -> list[Position] | None:
    """Shortest believed-passable path from start to goal, or None.

    The path lists every step after `start`, ending at `goal`. The search
    graph is finite (memory records only) and the closed set bounds it, so
    unreachable goals terminate; an expansion cap guards against regressions.
    """
    if not memory.believes_passable(start) or not memory.believes_passable(goal):
        return None
    bound = 8 * (len(memory) + 1)  # exceeds the whole graph; pure paranoia
    counter = 0
    open_heap: list[tuple[float, float, int, Position]] = [(_octile(start, goal), 0.0, 0, start)]
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
        for nxt, step in _neighbors(memory, pos):
            tentative = g + step
            if nxt in closed or (nxt in g_score and g_score[nxt] <= tentative):
                continue
            g_score[nxt] = tentative
            came_from[nxt] = pos
            counter += 1
            heapq.heappush(open_heap, (tentative + _octile(nxt, goal), tentative, counter, nxt))
    return None


def distances(
    memory: Memory,
    start: Position,
    targets: Iterable[Position] | None = None,
    max_expansions: int | None = None,
    stop_after: int | None = None,
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
        for nxt, step in _neighbors(memory, pos):
            tentative = g + step
            if nxt in closed or (nxt in cost and cost[nxt] <= tentative):
                continue
            cost[nxt] = tentative
            came_from[nxt] = pos
            counter += 1
            heapq.heappush(open_heap, (tentative, counter, nxt))
    return cost, came_from


def rebuild_path(came_from: Mapping[Position, Position], goal: Position, start: Position) -> list[Position]:
    """Walk the from-links back from goal; steps after start, goal included."""
    if goal == start:
        return []
    path = [goal]
    while path[-1] in came_from and came_from[path[-1]] != start:
        path.append(came_from[path[-1]])
    path.reverse()
    return path
