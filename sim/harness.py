"""Headless soak harness: build world + agent, tick N times, report stats.

No pygame, no rendering — the referee box for watching EXPLORE clear a
finite dungeon. Coverage is measured against world truth here only (a
metric, not a brain input); the agent inside the loop still sees nothing
but its own memory.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from config import DEFAULT_CONFIG, Config
from sim.tick import AgentState, tick
from world.gen_bsp import generate
from world.tiles import Tile

Position = tuple[int, int]


@dataclass(frozen=True)
class SimStats:
    """What a soak run measured."""

    ticks: int
    seed: int
    coverage: float  # fraction of reachable floor ever seen
    memory_tiles: int  # total records (floors + walls) in memory
    decisions: int  # EXPLORE decisions made
    final_position: Position


def spawn_position(tiles: Sequence[Sequence[Tile]], center_x: int, center_y: int) -> Position:
    """Deterministic spawn: the FLOOR cell nearest the map center."""
    floors = (
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile is Tile.FLOOR
    )
    return min(floors, key=lambda p: (p[0] - center_x) ** 2 + (p[1] - center_y) ** 2)


def reachable_floors(tiles: Sequence[Sequence[Tile]], start: Position) -> set[Position]:
    """Truth-side flood fill from start with the agent's movement rules
    (8-dir, no corner cutting) — the denominator of coverage."""
    seen = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if dx != 0 and dy != 0:
                    if tiles[y][x + dx] is not Tile.FLOOR or tiles[y + dy][x] is not Tile.FLOOR:
                        continue
                nxt = (x + dx, y + dy)
                if nxt in seen:
                    continue
                if tiles[nxt[1]][nxt[0]] is Tile.FLOOR:
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


def run_ticks(n: int, seed: int, config: Config = DEFAULT_CONFIG) -> SimStats:
    """Generate the world from `seed`, run the agent for n ticks, measure.

    Deterministic end to end: same (n, seed, config) -> identical stats.
    """
    tiles = generate(
        random.Random(seed),
        config.map_width,
        config.map_height,
        config.bsp_min_partition,
        config.bsp_min_room,
    )
    rng = random.Random(seed + 1)
    spawn = spawn_position(tiles, config.map_width // 2, config.map_height // 2)
    agent = AgentState(x=spawn[0], y=spawn[1])
    for _ in range(n):
        tick(agent, tiles, rng, config)
    reachable = reachable_floors(tiles, spawn)
    seen = sum(
        1
        for coord in agent.memory.known()
        if coord in reachable and agent.memory.terrain(coord) is Tile.FLOOR
    )
    return SimStats(
        ticks=n,
        seed=seed,
        coverage=seen / len(reachable),
        memory_tiles=len(agent.memory),
        decisions=agent.explorer.decisions,
        final_position=(agent.x, agent.y),
    )
