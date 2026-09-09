"""Sparse memory: everything the agent brain is allowed to know about the world.

Records exist only for tiles the FOV has delivered; the dict is keyed by
(x, y) and never consulted for tiles outside it. Terrain beliefs are written
by `observe` from FOV output — memory itself never touches the world grid.
Entity/item snapshot fields join the record in later phases; callers read
records by attribute so the dataclass can grow without breaking them.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from world.tiles import Tile

Position = tuple[int, int]


@dataclass
class MemoryRecord:
    """One tile's belief: what terrain it is and when it was last seen."""

    terrain_belief: Tile
    last_seen_tick: int


class Memory:
    """Sparse (x, y) -> MemoryRecord map; the brain's only world model."""

    def __init__(self) -> None:
        self._records: dict[Position, MemoryRecord] = {}
        self.generation: int = 0  # bumps once per observe that adds new tiles

    def observe(self, observation: Mapping[Position, Tile], tick: int) -> int:
        """Merge one FOV observation (visible coord -> terrain) into memory.

        Returns how many tiles were previously unknown. Re-sightings only
        refresh `last_seen_tick`.
        """
        fresh = 0
        for coord, terrain in observation.items():
            record = self._records.get(coord)
            if record is None:
                self._records[coord] = MemoryRecord(terrain_belief=terrain, last_seen_tick=tick)
                fresh += 1
            else:
                record.last_seen_tick = tick
        if fresh:
            self.generation += 1
        return fresh

    def believes_passable(self, coord: Position) -> bool:
        """True only for tiles already seen AND believed to be floor."""
        record = self._records.get(coord)
        return record is not None and record.terrain_belief.passable

    def known(self) -> Iterable[Position]:
        """Iterate the coordinates memory has records for."""
        return iter(self._records.keys())

    def terrain(self, coord: Position) -> Tile | None:
        """The believed terrain at coord, or None when never seen."""
        record = self._records.get(coord)
        return None if record is None else record.terrain_belief

    def age(self, coord: Position, tick: int) -> int:
        """Ticks since the last sighting of coord; KeyError when unseen."""
        return tick - self._records[coord].last_seen_tick

    def __contains__(self, coord: object) -> bool:
        return coord in self._records

    def __len__(self) -> int:
        return len(self._records)
