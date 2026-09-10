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

# The eight neighbours, spelled out here rather than imported from pathing:
# pathing imports this module, and a cycle to share a constant is a poor trade.
_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))


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
        # Believed-passable tiles with at least one unknown neighbour, kept up
        # to date rather than searched for. Recomputing it meant walking every
        # remembered tile on every decision, which is fine at a thousand tiles
        # and the most expensive thing in the run at forty thousand. A tile's
        # membership can only change when a neighbour becomes known or is
        # forgotten, so an addition or a removal refreshes nine tiles.
        self._frontier: set[Position] = set()

    def observe(
        self,
        observation: Mapping[Position, Tile],
        tick: int,
        entities: Mapping[Position, str] | None = None,
        items: Mapping[Position, str] | None = None,
        snapshot_coords: set | None = None,
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
        new_tiles: list[Position] = []
        changed: list[Position] = []
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
                new_tiles.append(coord)
            elif snapshot_coords is None or coord in snapshot_coords:
                if record.terrain_belief is not terrain:
                    # Terrain is static in this world, so this is rare - but a
                    # belief that changes changes the tile's own frontier
                    # status, and an invariant that only holds while nothing
                    # surprising happens is not an invariant. Only the tile
                    # itself: its neighbours care whether it is *known*, which
                    # has not changed.
                    changed.append(coord)
                record.last_seen_tick = tick
                record.terrain_belief = terrain
                record.last_entity_snapshot = entities.get(coord)
                record.last_item = items.get(coord)
            else:
                # Lit, not seen. Update the terrain belief, but do NOT touch
                # the clock: light is not a sighting. Refreshing it here keeps
                # the record alive forever, and with it whatever monster the
                # agent last saw on that tile - an immortal phantom that keeps
                # the threat field hot and can pin the agent in flight for the
                # rest of the run.
                record.terrain_belief = terrain
                continue
            self._index(coord, entities.get(coord), items.get(coord))
        for coord in new_tiles:
            self._refresh_around(coord)
        for coord in changed:
            self._refresh_frontier(coord)
        if fresh:
            self.generation += 1
        return fresh

    def _is_frontier(self, coord: Position) -> bool:
        record = self._records.get(coord)
        if record is None or not record.terrain_belief.passable:
            return False
        x, y = coord
        for dx, dy in _NEIGHBOURS:
            if (x + dx, y + dy) not in self._records:
                return True
        return False

    def _refresh_frontier(self, coord: Position) -> None:
        """Bring one tile's frontier membership back in line with the records."""
        if self._is_frontier(coord):
            self._frontier.add(coord)
        else:
            self._frontier.discard(coord)

    def _refresh_around(self, coord: Position) -> None:
        """Refresh a tile and its neighbours, after it appeared or vanished."""
        self._refresh_frontier(coord)
        x, y = coord
        for dx, dy in _NEIGHBOURS:
            self._refresh_frontier((x + dx, y + dy))

    def frontier(self) -> set:
        """Tiles believed passable that still border something unseen."""
        return self._frontier

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
        for coord in expired:
            # After every removal, not during: a tile whose neighbour is also
            # about to go would otherwise be judged against a half-pruned map.
            self._refresh_around(coord)
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
            self._refresh_around(coord)
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
