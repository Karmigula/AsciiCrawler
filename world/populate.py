"""Per-chunk population: monsters, items and hidden traps, placed at generation.

This module places things; `sim.ai` moves them and `sim.combat` kills them.
What matters here is that placement is *deterministic* and *scales with depth*: a chunk populated from (world_seed, cx, cy) holds the same
spawns forever, and the further that chunk sits from the world origin the more
monsters it holds and the deeper the table they roll from.

Distance is Euclidean from the world origin measured at the chunk-center tile
— the same metric and sample point `chunks._band_for` uses for biome bands, so
depth and biome move together instead of drifting apart.

Respawn (Phase 4): a chunk the agent has cleared refills slowly, but only
while the agent is far from it — refilling a chunk somebody is standing in
would read as monsters materialising out of the air. `respawn_tick` is the
next tick this chunk may add anything, and `respawn_cap` is its ceiling.
"""

import math
import random
from dataclasses import dataclass, field

import numpy as np

from config import Config
from sim.affixes import describe
from sim.items import ITEMS, ItemKind, roll_for
from sim.monsters import MAX_TIER, MonsterKind, table_for_tier
from world.tiles import Tile

Position = tuple[int, int]


@dataclass
class Monster:
    """A placed monster. Mutable: Phase 4 damages `hp` and moves it."""

    kind: MonsterKind
    x: int
    y: int
    hp: int
    last_moved_tick: int = -1  # guards against acting twice in one tick


@dataclass(frozen=True)
class Item:
    """A placed item: a base kind plus whatever the affix roll gave it."""

    kind: ItemKind
    x: int
    y: int
    rarity: str = "common"
    affixes: tuple = ()

    @property
    def attack(self) -> int:
        """Base attack plus every stat/curse affix that touches attack."""
        return self.kind.attack + sum(
            int(a.amount) for a in self.affixes if a.field == "attack"
        )

    @property
    def defense(self) -> int:
        return self.kind.defense + sum(
            int(a.amount) for a in self.affixes if a.field == "defense"
        )

    @property
    def name(self) -> str:
        return describe(self.kind.key, self.affixes)

    @property
    def cursed(self) -> bool:
        return any(a.is_curse for a in self.affixes)


@dataclass
class Trap:
    """A placed trap. Hidden until the agent spots it or steps in it."""

    x: int
    y: int
    hidden: bool = True


@dataclass
class ChunkContents:
    """Everything living (or lying) in one chunk, in global coordinates."""

    monsters: list[Monster] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    traps: list[Trap] = field(default_factory=list)
    respawn_tick: int = 0  # Phase 4 reads this; nothing ticks it yet
    respawn_cap: int = 0

    # Position indexes over the lists above. They are rebuilt on demand rather
    # than maintained: the tick queries them once per visible tile every tick,
    # and a linear scan there costs (visible tiles x monsters) per tick, which
    # is enough to dominate a soak run. Phase 4 moves and kills monsters, so it
    # must call `invalidate()` (or go through helpers that do) after mutating
    # `monsters`; a stale index is the obvious trap here and this is the note
    # that says so.
    _entity_index: dict[Position, Monster] | None = field(
        default=None, repr=False, compare=False
    )
    _item_index: dict[Position, Item] | None = field(
        default=None, repr=False, compare=False
    )

    def invalidate(self) -> None:
        """Drop the position indexes; call after mutating monsters or items."""
        self._entity_index = None
        self._item_index = None

    def entity_at(self, x: int, y: int) -> Monster | None:
        if self._entity_index is None:
            self._entity_index = {(m.x, m.y): m for m in self.monsters}
        return self._entity_index.get((x, y))

    def item_at(self, x: int, y: int) -> Item | None:
        if self._item_index is None:
            self._item_index = {(i.x, i.y): i for i in self.items}
        return self._item_index.get((x, y))

    def trap_at(self, x: int, y: int) -> "Trap | None":
        for trap in self.traps:
            if trap.x == x and trap.y == y:
                return trap
        return None


def chunk_distance(cx: int, cy: int, config: Config) -> float:
    """Euclidean distance from the world origin to the chunk-center tile."""
    size = config.chunk_size
    gx = cx * size + size // 2
    gy = cy * size + size // 2
    return math.hypot(gx, gy)


def depth_fraction(cx: int, cy: int, config: Config) -> float:
    """0.0 at the origin, 1.0 at and beyond `tier_distance_max`."""
    if config.tier_distance_max <= 0:
        return 1.0
    return min(1.0, chunk_distance(cx, cy, config) / config.tier_distance_max)


def max_tier_for(cx: int, cy: int, config: Config) -> int:
    """Deepest monster tier this chunk may roll — monotone in distance."""
    return min(MAX_TIER, int(depth_fraction(cx, cy, config) * (MAX_TIER + 1)))


def populate(
    rng: random.Random, tiles: np.ndarray, cx: int, cy: int, config: Config
) -> ChunkContents:
    """Roll this chunk's contents from its own seeded rng. Never mutates tiles.

    Spawns land only on FLOOR (liquids are impassable, so anything standing in
    one would be unreachable for good) and never on the chunk-center tile,
    which the pipeline carves as its connectivity anchor and chunk (0, 0) uses
    as the agent's spawn.
    """
    size = config.chunk_size
    center = (size // 2, size // 2)
    floor = int(Tile.FLOOR)
    cells = tiles.tolist()
    spots = [
        (x, y)
        for y in range(tiles.shape[0])
        for x in range(tiles.shape[1])
        if cells[y][x] == floor and (x, y) != center
    ]
    contents = ChunkContents(respawn_cap=config.respawn_cap_per_chunk)
    if not spots:
        return contents

    fraction = depth_fraction(cx, cy, config)
    density = config.spawn_density_near + fraction * (
        config.spawn_density_far - config.spawn_density_near
    )
    table = table_for_tier(max_tier_for(cx, cy, config))

    rng.shuffle(spots)
    taken = iter(spots)  # one shared pool: nothing shares a tile with anything

    def take(count: int) -> list[Position]:
        picked: list[Position] = []
        for _ in range(count):
            spot = next(taken, None)
            if spot is None:
                break
            picked.append(spot)
        return picked

    # No cap on the initial roll: respawn_cap is Phase 4's ceiling on monsters
    # trickling *back* into a cleared chunk, and clamping the first population
    # with it would flatten the depth curve wherever the cap bites first.
    monster_count = round(density * len(spots))
    origin_x, origin_y = cx * size, cy * size
    for x, y in take(monster_count):
        kind = table[rng.randrange(len(table))]
        contents.monsters.append(
            Monster(kind=kind, x=origin_x + x, y=origin_y + y, hp=kind.hp)
        )
    for x, y in take(round(config.item_density * len(spots))):
        kind = ITEMS[rng.randrange(len(ITEMS))]
        rarity, affixes = roll_for(kind, rng, fraction, config)
        contents.items.append(
            Item(
                kind=kind,
                x=origin_x + x,
                y=origin_y + y,
                rarity=rarity,
                affixes=affixes,
            )
        )
    for x, y in take(round(config.trap_density * len(spots))):
        contents.traps.append(Trap(x=origin_x + x, y=origin_y + y))
    return contents


def try_respawn(
    rng: random.Random,
    tiles: np.ndarray,
    cx: int,
    cy: int,
    contents: ChunkContents,
    config: Config,
    tick: int,
) -> Monster | None:
    """Add one monster to a thinned-out chunk, or return None.

    Deliberately one at a time: a cleared chunk should refill over minutes of
    watching, not snap back to full the moment the agent turns their back.
    """
    if tick < contents.respawn_tick or len(contents.monsters) >= contents.respawn_cap:
        return None
    size = config.chunk_size
    centre = (size // 2, size // 2)
    floor = int(Tile.FLOOR)
    cells = tiles.tolist()
    occupied = {(m.x - cx * size, m.y - cy * size) for m in contents.monsters}
    spots = [
        (x, y)
        for y in range(tiles.shape[0])
        for x in range(tiles.shape[1])
        if cells[y][x] == floor and (x, y) != centre and (x, y) not in occupied
    ]
    contents.respawn_tick = tick + config.respawn_cooldown_ticks
    if not spots:
        return None
    x, y = spots[rng.randrange(len(spots))]
    table = table_for_tier(max_tier_for(cx, cy, config))
    kind = table[rng.randrange(len(table))]
    monster = Monster(kind=kind, x=cx * size + x, y=cy * size + y, hp=kind.hp)
    contents.monsters.append(monster)
    contents.invalidate()
    return monster
