"""Utility goals. EXPLORE is the first (and so far only) one implemented.

EXPLORE scores frontier candidates with
    score = w_explore * info_gain / (1 + path_cost)
where info_gain counts the never-seen tiles adjacent to the candidate and
path_cost is the shortest-path cost over believed floors (one Dijkstra
sweep whose values equal each candidate's A* path length — see pathing).
Hysteresis keeps the incumbent target from being dithered away by a
near-tied challenger, and small seeded noise breaks exact ties between
identical candidates.

Everything here reads memory only — the world grid is invisible to goals.
"""

import random
from dataclasses import dataclass, field

from agent.memory import Memory, Position
from agent.pathing import DIRS_8, distances, rebuild_path
from config import Config

Decision = tuple[Position, list[Position]]  # (target, steps after start)


def frontier(memory: Memory) -> list[Position]:
    """Believed-floor tiles with at least one never-seen 8-neighbour.

    Off-map neighbours cannot bite: the generator keeps a wall border, so a
    floor's neighbours are always in-bounds and 'unknown' means unseen-yet.
    """
    result = []
    for coord in memory.known():
        if not memory.believes_passable(coord):
            continue
        x, y = coord
        if any((x + dx, y + dy) not in memory for dx, dy in DIRS_8):
            result.append(coord)
    return result


def info_gain(memory: Memory, coord: Position) -> int:
    """How many never-seen tiles are adjacent to coord (the prize on offer)."""
    x, y = coord
    return sum(1 for dx, dy in DIRS_8 if (x + dx, y + dy) not in memory)


@dataclass
class ExploreGoal:
    """Stateful EXPLORE: incumbent target, current path, decision bookkeeping."""

    target: Position | None = None
    path: list[Position] = field(default_factory=list)
    decisions: int = 0
    yielded: bool = False
    _ever_decided: bool = field(default=False)
    _last_decision_tick: int = 0
    _decided_at_generation: int = -1

    def decide(
        self,
        start: Position,
        memory: Memory,
        rng: random.Random,
        config: Config,
        tick: int = 0,
    ) -> Decision | None:
        """Re-score the frontier from `start`; adopt the best target or yield.

        Yields (returns None, clears the plan) when no frontier exists or no
        candidate is reachable in belief — the caller falls back to wandering.
        """
        candidates = frontier(memory)
        if candidates:
            sx, sy = start
            candidates.sort(key=lambda p: (max(abs(p[0] - sx), abs(p[1] - sy)), p))
            del candidates[config.frontier_sample_size:]
            cost, came_from = distances(memory, start)
            best: Position | None = None
            best_score = float("-inf")
            for cand in candidates:
                path_cost = cost.get(cand)
                if path_cost is None:
                    continue
                score = config.w_explore * info_gain(memory, cand) / (1.0 + path_cost)
                if cand == self.target:
                    score += config.explore_hysteresis_bonus
                score += rng.uniform(-config.explore_noise, config.explore_noise)
                if score > best_score:
                    best, best_score = cand, score
        else:
            best = None
        self._last_decision_tick = tick
        self._decided_at_generation = memory.generation
        self._ever_decided = True
        self.decisions += 1
        if best is None:
            self.target = None
            self.path = []
            self.yielded = True
            return None
        self.target = best
        self.path = rebuild_path(came_from, best, start)
        self.yielded = False
        return best, self.path

    def drop_plan(self) -> None:
        """Event hook for a blocked path: forget the plan, keep the incumbent."""
        self.path = []

    def wants_rethink(self, memory: Memory, tick: int, throttle_ticks: int) -> bool:
        """Decision throttle: events fire now; otherwise ~every N ticks.

        Re-scoring with unchanged knowledge is pure churn (identical scores,
        hysteresis holds), so a rethink needs fresh memory unless the plan is
        gone — reached target, blocked path, or never decided yet.
        """
        if not self._ever_decided:
            return True
        if not self.path:
            if self.yielded:
                return memory.generation != self._decided_at_generation
            return True  # plan exhausted or blocked mid-route: event
        return (
            tick - self._last_decision_tick >= throttle_ticks
            and memory.generation != self._decided_at_generation
        )
