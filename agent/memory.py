"""Sparse memory: everything the agent brain is allowed to know about the world.

Records exist only for tiles the FOV has delivered; the dict is keyed by
(x, y) and never consulted for tiles outside it. Terrain beliefs are written
by `observe` from FOV output — memory itself never touches the world grid.

Memory is mortal. A record older than `ttl` ticks is expired: `prune` drops
it and the tile becomes unknown again, exactly as if it had never been seen.
That is what keeps the dict bounded by recent experience rather than lifetime
experience, and what keeps the world interesting — forgotten ground reappears
as frontier, so the agent re-explores it forever instead of running out of
novelty. Because expiry is measured in ticks since last sighting, the tick
loop must observe every tick: the timestamps are load-bearing.

Records also carry what was last *seen on* a tile (entity glyph, item glyph)
so the renderer can ghost remembered monsters and loot at their last known
position. A sighting that finds the tile empty clears those snapshots — the
agent believes what it last saw, including seeing something gone.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from world.tiles import Tile

Position = tuple[int, int]


@dataclass
class MemoryRecord:
    """One tile's belief: terrain, when last seen, and what stood on it."""

    terrain_belief: Tile
    last_seen_tick: int
    last_entity_snapshot: str | None = None
    last_item: str | None = None
    known_trap: bool = False


class Memory:
    """Sparse (x, y) -> MemoryRecord map; the brain's only world model."""

    def __init__(self) -> None:
        self._records: dict[Position, MemoryRecord] = {}
        self.generation: int = 0  # bumps once per observe that adds new tiles
        # Coordinates whose record currently holds a monster or an item
        # snapshot. Maintained rather than searched: the threat field samples
        # danger per candidate tile (and per node of the FLEE search), and
        # scanning a square of memory for each of those made the sweep the
        # single most expensive thing in a long run. These sets are small -
        # what the agent has recently seen, not what it remembers.
        self._entity_coords: set[Position] = set()
        self._item_coords: set[Position] = set()

    def observe(
        self,
        observation: Mapping[Position, Tile],
        tick: int,
        entities: Mapping[Position, str] | None = None,
        items: Mapping[Position, str] | None = None,
    ) -> int:
        """Merge one FOV observation (visible coord -> terrain) into memory.

        Returns how many tiles were previously unknown. A re-sighting refreshes
        `last_seen_tick`, re-writes the terrain belief (static today, but the
        record is the belief of record) and overwrites both snapshots from what
        is visible now — including overwriting them with None when the tile is
        seen to be empty.
        """
        entities = entities or {}
        items = items or {}
        fresh = 0
        for coord, terrain in observation.items():
            record = self._records.get(coord)
            if record is None:
                self._records[coord] = MemoryRecord(
                    terrain_belief=terrain,
                    last_seen_tick=tick,
                    last_entity_snapshot=entities.get(coord),
                    last_item=items.get(coord),
                )
                fresh += 1
            else:
                record.last_seen_tick = tick
                record.terrain_belief = terrain
                record.last_entity_snapshot = entities.get(coord)
                record.last_item = items.get(coord)
            self._index(coord, entities.get(coord), items.get(coord))
        if fresh:
            self.generation += 1
        return fresh

    def _index(self, coord: Position, entity: str | None, item: str | None) -> None:
        """Keep the snapshot indexes in step with a record that just changed."""
        if entity is None:
            self._entity_coords.discard(coord)
        else:
            self._entity_coords.add(coord)
        if item is None:
            self._item_coords.discard(coord)
        else:
            self._item_coords.add(coord)

    def entity_coords(self) -> set:
        """Coordinates where memory believes a monster is standing."""
        return self._entity_coords

    def item_coords(self) -> set:
        """Coordinates where memory believes an item is lying."""
        return self._item_coords

    def prune(self, tick: int, ttl: int) -> int:
        """Drop every record older than `ttl` ticks. Returns how many went.

        Bumps `generation` when anything is dropped: forgetting changes the
        frontier just as much as discovering does, and a brain that caches its
        plan against the generation counter must re-look at a world it has
        started to forget.
        """
        expired = [
            coord
            for coord, record in self._records.items()
            if tick - record.last_seen_tick > ttl
        ]
        for coord in expired:
            del self._records[coord]
            self._entity_coords.discard(coord)
            self._item_coords.discard(coord)
        if expired:
            self.generation += 1
        return len(expired)

    def mark_hazard(self, coord: Position, tick: int, terrain: Tile) -> None:
        """Remember that this tile has a trap in it.

        Survives re-sighting, unlike the entity and item snapshots: a trap the
        agent has spotted does not become invisible again just because it
        looked a second time. It is forgotten only when the record is pruned,
        which is decay doing its job — the agent really can walk back into a
        trap it has forgotten about.
        """
        record = self._records.get(coord)
        if record is None:
            record = MemoryRecord(terrain_belief=terrain, last_seen_tick=tick)
            self._records[coord] = record
            self.generation += 1
        record.known_trap = True

    def believes_hazard(self, coord: Position) -> bool:
        """True for tiles the agent knows to be trapped."""
        record = self._records.get(coord)
        return record is not None and record.known_trap

    def snapshot(self, coord: Position) -> tuple[str | None, str | None]:
        """(entity glyph, item glyph) last seen on coord; (None, None) if unseen."""
        record = self._records.get(coord)
        if record is None:
            return None, None
        return record.last_entity_snapshot, record.last_item

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
