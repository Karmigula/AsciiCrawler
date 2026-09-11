"""Utility goals: EXPLORE, and FLEE which can take the wheel off it.

EXPLORE scores frontier candidates with
    score = w_explore * info_gain / (1 + path_cost)
where info_gain counts the never-seen tiles adjacent to the candidate and
path_cost is the shortest-path cost over believed floors (one Dijkstra
sweep whose values equal each candidate's A* path length — see pathing).
The sweep is bounded by the sampled candidates: it stops once they have all
been settled, which costs a fraction of a full sweep over everything the
agent remembers and returns the identical costs for the coords being scored.
Hysteresis keeps the incumbent target from being dithered away by a
near-tied challenger, and small seeded noise breaks exact ties between
identical candidates.

FLEE is an override rather than another scored option. A utility comparison
between "look at something new" and "do not die" invites the agent to be
talked into a slightly better exploration score while a troll eats it; making
fear pre-empt the score instead means the decision is legible from outside,
which is the point of an aquarium. It releases on hysteresis (flee_release) so
the agent does not flicker on the threshold.

Threat enters EXPLORE as a discount on each candidate, so the agent prefers
frontier away from what it remembers even when it is not frightened enough to
run. Both read the threat field, which reads memory — see agent/threat.py.

Everything here reads memory only — the world grid is invisible to goals.
"""

import random
from dataclasses import dataclass, field

from agent.memory import Memory, Position
from agent.pathing import DIRS_8, StepCosts, distances, rebuild_path
from agent.threat import danger, flee_threshold
from config import Config
from sim.items import ITEMS

ITEM_BY_GLYPH = {kind.glyph: kind for kind in ITEMS}
SHRINE_GLYPH = "&"
SHOP_GLYPH = "%"

Decision = tuple[Position, list[Position]]  # (target, steps after start)


def frontier(memory: Memory) -> list[Position]:
    """Believed-floor tiles with at least one never-seen 8-neighbour.

    Read from the set memory maintains rather than recomputed. Walking all of
    memory here cost more than everything else the brain did put together once
    the agent remembered tens of thousands of tiles.

    Off-map neighbours cannot bite: the generator keeps a wall border, so a
    floor's neighbours are always in-bounds and 'unknown' means unseen-yet.
    """
    return list(memory.frontier())


def info_gain(memory: Memory, coord: Position) -> int:
    """How many never-seen tiles are adjacent to coord (the prize on offer)."""
    x, y = coord
    return sum(1 for dx, dy in DIRS_8 if (x + dx, y + dy) not in memory)


def opens_onto(memory: Memory, coord: Position, radius: int) -> int:
    """Unknown tiles within `radius` - how much *world* is behind this one.

    `info_gain` looks one tile out, which cannot tell the mouth of an
    unexplored region from a dent in a wall the agent has already walked: both
    show three unknown neighbours. Looking further sees the difference, and
    the difference is the whole question of where to go next.
    """
    x, y = coord
    return sum(
        1
        for dy in range(-radius, radius + 1)
        for dx in range(-radius, radius + 1)
        if (dx or dy) and (x + dx, y + dy) not in memory
    )


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
        all_frontier = frontier(memory)
        best: Position | None = None
        came_from: dict[Position, Position] = {}
        if all_frontier:
            sx, sy = start
            all_frontier.sort(key=lambda p: (max(abs(p[0] - sx), abs(p[1] - sy)), p))
            sample = all_frontier[: config.frontier_sample_size]
            best, came_from = self._best_of(sample, start, memory, rng, config)
            if best is None and len(all_frontier) > len(sample):
                # Every nearby candidate was unreachable in belief. The sample
                # is taken by straight-line distance, so that says nothing
                # about the frontier beyond it — a wall the agent has not yet
                # found a way around puts the whole neighbourhood out of reach
                # while perfectly good frontier waits behind it. Pay for the
                # full sweep rather than falsely report nowhere left to go.
                best, came_from = self._best_of(
                    all_frontier, start, memory, rng, config
                )
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

    def _best_of(self, candidates, start, memory, rng, config):
        """Score a candidate list; return (best, came_from) or (None, {})."""
        cost, came_from = distances(
            memory,
            start,
            targets=candidates,
            max_expansions=config.path_expansion_cap,
            stop_after=config.plan_settle_target,
            costs=StepCosts.from_config(config),
        )
        best: Position | None = None
        best_score = float("-inf")
        for cand in candidates:
            path_cost = cost.get(cand)
            if path_cost is None:
                continue
            prize = info_gain(memory, cand) + config.w_frontier_reach * opens_onto(
                memory, cand, config.frontier_lookahead
            )
            # Distance still counts against a candidate, but less than
            # linearly: at an exponent of one the agent takes whatever is
            # nearest and works outward a tile at a time, which reads as
            # pottering. Below one, somewhere genuinely new is worth the walk.
            score = config.w_explore * prize / (1.0 + path_cost) ** config.explore_distance_falloff
            score -= config.w_threat * danger(memory, cand, config)
            if cand == self.target:
                score += config.explore_hysteresis_bonus
            score += rng.uniform(-config.explore_noise, config.explore_noise)
            if score > best_score:
                best, best_score = cand, score
        return best, came_from

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


@dataclass
class FleeGoal:
    """Get away from what the agent believes is dangerous. Overrides EXPLORE."""

    active: bool = False
    path: list[Position] = field(default_factory=list)
    flights: int = 0
    cornered_until: int = -1
    started_tick: int = 0

    def wants_control(
        self,
        start: Position,
        memory: Memory,
        stats,
        config: Config,
        derived=None,
        tick: int = 0,
    ) -> bool:
        """True while the believed danger here is more than the agent will take.

        Hysteresis on release: once running, it keeps running until danger
        drops well under the trigger, so the agent does not stutter in and out
        of flight on the boundary.
        """
        if tick < self.cornered_until:
            return False  # recently cornered: give it a moment to get clear
        if self.active and tick - self.started_tick > config.flee_max_ticks:
            # This flight is not working. Penned between two threats the agent
            # can outrun neither of, it would otherwise run back and forth
            # between them until something killed it.
            return False
        here = danger(memory, start, config)
        threshold = flee_threshold(stats, config, derived)
        if self.active:
            return here > threshold * config.flee_release
        return here > threshold

    def decide(
        self, start: Position, memory: Memory, config: Config, tick: int = 0
    ) -> list[Position]:
        """Walk believed-passable ground to the calmest tile within reach.

        A local breadth-first sweep, not a path to safety in general: fleeing
        is a decision that has to be remade constantly as the picture changes,
        so paying for a long plan would be waste.

        Returns the route, which is empty when nowhere within reach is calmer
        than where the agent already stands. The caller uses that to tell
        running away from being cornered.
        """
        if not self.active:
            self.flights += 1  # count flights, not ticks spent running
            self.started_tick = tick
        self.active = True
        best, best_key, came_from = start, None, {}
        seen = {start}
        queue = [(start, 0)]
        while queue:
            coord, depth = queue.pop(0)
            key = (danger(memory, coord, config), -depth, coord)
            if best_key is None or key < best_key:
                best, best_key = coord, key
            if depth >= config.flee_search_radius:
                continue
            x, y = coord
            for dx, dy in DIRS_8:
                nxt = (x + dx, y + dy)
                if nxt in seen or not memory.believes_passable(nxt):
                    continue
                if dx and dy and not (
                    memory.believes_passable((x + dx, y))
                    and memory.believes_passable((x, y + dy))
                ):
                    continue
                seen.add(nxt)
                came_from[nxt] = coord
                queue.append((nxt, depth + 1))
        self.path = rebuild_path(came_from, best, start) if best != start else []
        return self.path

    def stand_down(self, cornered_until: int = -1) -> None:
        """Danger has passed - or cannot be escaped: hand control back.

        `cornered_until` suppresses further flight for a while, which is what
        the caller passes when the agent gave up rather than got clear.
        """
        self.active = False
        self.path = []
        self.cornered_until = max(self.cornered_until, cornered_until)

    def drop_plan(self) -> None:
        """Blocked mid-flight: forget the route, keep running."""
        self.path = []


def expected_upgrade(
    glyph: str,
    equipped: dict,
    config: Config,
    potions: int = 0,
    health: float = 1.0,
    gold: int = 0,
) -> float:
    """What the agent *guesses* a remembered item is worth, from its glyph alone.

    This is the belief rule applied to loot. Memory holds a glyph, not an item:
    the agent knows there is a weapon over there, not that it is a cruel sword
    of the long mind. So LOOT prices an empty slot highly and a filled one
    modestly, and the agent walks over to find out - which is exactly how a
    creature without x-ray vision would behave.

    A potion is priced by need rather than at a flat rate. It used to be worth
    the same as a coin whether the creature had none and was bleeding or
    twenty and untouched, which is why it so rarely had one when it mattered:
    over twenty thousand ticks it spent 1,219 of them hurt enough to drink and
    was holding a potion for 66 of those.
    """
    if glyph == SHOP_GLYPH:
        # Worth the walk in proportion to what it could spend there. A stall
        # is scenery to a creature with no gold, and the reason to stoop for
        # coins in the first place to one with a purse.
        purse = min(1.0, gold / max(1, config.shop_interest_gold))
        return config.loot_expectation * config.w_shop * purse
    if glyph == SHRINE_GLYPH:
        # A totem is a question, not a prize. The agent knows there is one
        # over there and nothing else - not whether this biome's answers are
        # kind - so it is priced as curiosity, and curiosity is cheaper when
        # you are bleeding: a curse at full health is a nuisance, and a curse
        # at a fifth of it is the end of the run.
        return config.loot_expectation * config.w_shrine * min(1.0, health * 1.4)
    kind = ITEM_BY_GLYPH.get(glyph)
    if kind is None:
        return 0.0
    if kind.key == "gold":
        # Worth picking up on the way past, never worth a detour: nothing in
        # this world sells anything.
        return config.loot_expectation * config.w_gold
    if kind.key == "potion":
        shortage = max(0.0, 1.0 - potions / max(1, config.potion_reserve))
        hurt = max(0.0, 1.0 - health)
        return config.loot_expectation * (
            config.w_potion * (0.35 + shortage) * (1.0 + config.w_potion_hurt * hurt)
        )
    if kind.slot is None:
        return config.loot_expectation * 0.5
    if equipped.get(kind.slot) is None:
        return config.loot_expectation * 2.0  # an empty slot is a real prize
    return config.loot_expectation


@dataclass
class LootGoal:
    """Go and pick up something the agent believes is lying around."""

    target: Position | None = None
    path: list[Position] = field(default_factory=list)
    pickups: int = 0

    def decide(
        self,
        start: Position,
        memory: Memory,
        equipped: dict,
        config: Config,
        potions: int = 0,
        health: float = 1.0,
        skip=(),
        gold: int = 0,
    ) -> Decision | None:
        """Score remembered items by expected upgrade over path cost.

        Only tiles memory still holds an item snapshot for are considered, so
        loot the agent has forgotten stops calling to it - decay applies to
        greed as much as to geography.
        """
        candidates = []
        for coord in memory.item_coords():
            if coord in skip:
                continue  # a totem it has already asked
            glyph = memory.snapshot(coord)[1]
            if glyph is None:
                continue
            value = expected_upgrade(glyph, equipped, config, potions, health, gold)
            if value > 0:
                candidates.append((coord, value))
        if not candidates:
            self.target, self.path = None, []
            return None
        sx, sy = start
        candidates.sort(key=lambda c: (max(abs(c[0][0] - sx), abs(c[0][1] - sy)), c[0]))
        del candidates[config.frontier_sample_size:]
        cost, came_from = distances(
            memory,
            start,
            targets=[coord for coord, _ in candidates],
            max_expansions=config.path_expansion_cap,
            stop_after=config.plan_settle_target,
            costs=StepCosts.from_config(config),
        )
        best, best_score = None, 0.0
        for coord, value in candidates:
            path_cost = cost.get(coord)
            if path_cost is None:
                continue
            score = config.w_loot * value / (1.0 + path_cost)
            score -= config.w_threat * danger(memory, coord, config)
            if score > best_score:
                best, best_score = coord, score
        if best is None:
            self.target, self.path = None, []
            return None
        self.target = best
        self.path = rebuild_path(came_from, best, start)
        return best, self.path

    def drop_plan(self) -> None:
        self.path = []

    def clear(self) -> None:
        self.target, self.path = None, []
