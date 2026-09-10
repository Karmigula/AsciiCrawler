"""Chunk-world tests: seams (the important ones), determinism, connectivity,
biomes, liquids, streaming, spawn."""

import hashlib

import pytest

from config import DEFAULT_CONFIG
from world.chunks import ChunkStore
from world.tiles import Tile

SIZE = DEFAULT_CONFIG.chunk_size
MID = SIZE // 2
FLOOR = int(Tile.FLOOR)
WATER = int(Tile.WATER)
LAVA = int(Tile.LAVA)

SEEDS = (4242, 17, 20260909)
# grids of adjacent chunks: (cx0, cy0, nx, ny); picked to straddle all three
# biome bands and include negative chunk coordinates
GRIDS = ((-1, -1, 3, 3), (1, 1, 2, 2), (3, 4, 2, 2), (6, 6, 2, 2))
# guaranteed-BSP chunks (center distance 45/101 + blend 48 < 150)
NEAR_CHUNKS = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
# guaranteed cave/cavern chunks (center distance - blend > 150)
FAR_CHUNKS = ((5, 4), (5, 5), (6, 6), (10, 0), (0, 10), (-5, 5), (7, 0), (4, 6))
# guaranteed cavern even at maximum blend noise (distance - 48 > 400)
CAVERNS = ((6, 6), (10, 0), (0, 10))


def _store(seed: int) -> ChunkStore:
    return ChunkStore(DEFAULT_CONFIG, world_seed=seed)


def _digest(store: ChunkStore, cx: int, cy: int) -> str:
    return hashlib.sha256(store.get_chunk(cx, cy).tiles.tobytes()).hexdigest()


def _merged(store: ChunkStore, cx0: int, cy0: int, nx: int, ny: int) -> list[list[int]]:
    """Tile rows of an nx*ny chunk grid starting at (cx0, cy0), global layout."""
    return [
        [
            int(store.get_chunk(cx0 + gx // SIZE, cy0 + gy // SIZE).tiles[gy % SIZE, gx % SIZE])
            for gx in range(nx * SIZE)
        ]
        for gy in range(ny * SIZE)
    ]


def _flood(grid: list[list[int]], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Agent-movement flood (8-dir, no corner cutting) over a merged grid."""
    height, width = len(grid), len(grid[0])
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (
                    not 0 <= nx < width
                    or not 0 <= ny < height
                    or grid[ny][nx] != FLOOR
                    or (nx, ny) in seen
                ):
                    continue
                if dx != 0 and dy != 0 and not (
                    grid[y][x + dx] == FLOOR and grid[y + dy][x] == FLOOR
                ):
                    continue
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def _long_wall_runs(grid: list[list[int]], min_len: int = 7) -> int:
    """Count maximal straight WALL runs >= min_len, both axes (room-likeness:
    measured 244+ on BSP chunks, <= 112 on CA chunks across test seeds)."""
    height, width = len(grid), len(grid[0])
    runs = 0
    for y in range(height):
        run = 0
        for x in range(width + 1):
            if x < width and grid[y][x] != FLOOR:
                run += 1
            else:
                if run >= min_len:
                    runs += 1
                run = 0
    for x in range(width):
        run = 0
        for y in range(height + 1):
            if y < height and grid[y][x] != FLOOR:
                run += 1
            else:
                if run >= min_len:
                    runs += 1
                run = 0
    return runs


# ---------------------------------------------------------------- seams


@pytest.mark.parametrize("seed", SEEDS)
def test_each_shared_border_has_exactly_one_mutually_passable_crossing(seed):
    """The seam invariant, black box: generators keep borders solid WALL, so
    the only mutually-passable adjacent pair on any internal border is the
    seam-corridor crossing — exactly one, near the edge midpoint."""
    for cx0, cy0, nx, ny in GRIDS:
        grid = _merged(_store(seed), cx0, cy0, nx, ny)
        for by in range(cy0, cy0 + ny):
            for bx in range(cx0, cx0 + nx - 1):  # vertical borders
                left = (bx - cx0 + 1) * SIZE - 1
                rows = [
                    (by - cy0) * SIZE + ly
                    for ly in range(SIZE)
                    if grid[(by - cy0) * SIZE + ly][left] == FLOOR
                    and grid[(by - cy0) * SIZE + ly][left + 1] == FLOOR
                ]
                assert len(rows) == 1, f"seed {seed}: V({bx},{by}) crossings {rows}"
                local = rows[0] - (by - cy0) * SIZE
                assert SIZE // 4 <= local < 3 * SIZE // 4
        for by in range(cy0, cy0 + ny - 1):  # horizontal borders
            for bx in range(cx0, cx0 + nx):
                top = (by - cy0 + 1) * SIZE - 1
                cols = [
                    (bx - cx0) * SIZE + lx
                    for lx in range(SIZE)
                    if grid[top][(bx - cx0) * SIZE + lx] == FLOOR
                    and grid[top + 1][(bx - cx0) * SIZE + lx] == FLOOR
                ]
                assert len(cols) == 1, f"seed {seed}: H({bx},{by}) crossings {cols}"
                local = cols[0] - (bx - cx0) * SIZE
                assert SIZE // 4 <= local < 3 * SIZE // 4


@pytest.mark.parametrize("seed", SEEDS)
def test_flood_fill_across_borders_merges_all_floor(seed):
    """Mutual passability, the strong form: one flood from a chunk center
    with the agent's movement rules reaches every FLOOR tile of the grid,
    crossing every internal border through the seam corridors."""
    for cx0, cy0, nx, ny in GRIDS:
        grid = _merged(_store(seed), cx0, cy0, nx, ny)
        start = (MID, MID)  # center of the (cx0, cy0) chunk, grid-local
        floors = {
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile == FLOOR
        }
        assert start in floors
        assert _flood(grid, start) == floors


# ---------------------------------------------------------- determinism


@pytest.mark.parametrize("cx, cy", ((0, 0), (-3, -2), (5, -7), (2, 2), (-1, 1)))
def test_same_seed_and_coords_generate_identical_chunks(cx, cy):
    assert _digest(_store(4242), cx, cy) == _digest(_store(4242), cx, cy)
    assert _digest(_store(4242), cx, cy) != _digest(_store(4243), cx, cy)


def test_chunk_generation_is_independent_of_neighbor_state():
    """No cross-chunk state: a chunk's tiles cannot depend on what was
    generated before it or around it."""
    lone = _store(77)
    expected = _digest(lone, 2, 2)
    surrounded = _store(77)
    for cy in range(1, 4):
        for cx in range(1, 4):
            surrounded.get_chunk(cx, cy)
    assert _digest(surrounded, 2, 2) == expected
    after = _store(77)
    after.get_chunk(2, 2)
    for cy in range(1, 4):
        for cx in range(1, 4):
            after.get_chunk(cx, cy)
    assert _digest(after, 2, 2) == expected


# -------------------------------------------------------- connectivity


@pytest.mark.parametrize("seed", (4242, 7))
@pytest.mark.parametrize("cx, cy", ((0, 0), (1, 1), (3, 3), (6, 6), (-2, -2), (10, 0)))
def test_all_floor_reachable_from_chunk_center(seed, cx, cy):
    """Interior connectivity across all three biomes (BSP, cave, cavern)."""
    grid = _store(seed).get_chunk(cx, cy).tiles.tolist()
    floors = {
        (x, y)
        for y, row in enumerate(grid)
        for x, tile in enumerate(row)
        if tile == FLOOR
    }
    assert (MID, MID) in floors
    assert _flood(grid, (MID, MID)) == floors


# --------------------------------------------------------------- biomes


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_each_biome_has_its_own_shape(seed):
    """Biome decides shape now, not distance.

    Measured with the long-wall-run count, which separates architecture from
    erosion. Medians over three seeds when this was written:

        warren 61   caverns 84   ashfields 85   caves 130   marsh 136
        crystal 194   ossuary 248   halls 294   ruins 298

    Asserted as bands rather than one global threshold, because two of these
    deliberately sit between the extremes: crystal is a cave smoothed until it
    has long clean faces, and the ossuary is architecture built out of niches
    rather than halls. A single cutoff called crystal a room and the ossuary a
    cave, which is exactly backwards.
    """
    import statistics
    from collections import defaultdict

    from world.biomes import biome_at

    store = _store(seed)
    runs = defaultdict(list)
    for cx in range(-6, 7):
        for cy in range(-6, 7):
            biome = biome_at(seed, cx, cy, DEFAULT_CONFIG)
            runs[biome.key].append(_long_wall_runs(store.get_chunk(cx, cy).tiles.tolist()))

    def median(key):
        return statistics.median(runs[key]) if runs.get(key) else None

    architectural = [median(k) for k in ("halls", "ruins", "ossuary") if median(k)]
    organic = [median(k) for k in ("warren", "caverns", "ashfields") if median(k)]
    assert architectural, f"seed {seed}: no built biomes in range"
    assert organic, f"seed {seed}: no eroded biomes in range"
    assert min(architectural) > 150, (seed, dict(runs.keys() and {}))
    assert max(organic) < 130, (seed, organic)
    assert min(architectural) > max(organic), "built places should read as built"


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_the_crystal_hollows_sit_between_cave_and_architecture(seed):
    """Its whole design is a cave smoothed until the faces go straight."""
    import statistics
    from collections import defaultdict

    from world.biomes import biome_at

    store = _store(seed)
    runs = defaultdict(list)
    for cx in range(-7, 8):
        for cy in range(-7, 8):
            biome = biome_at(seed, cx, cy, DEFAULT_CONFIG)
            if biome.key in ("crystal", "caves", "halls"):
                runs[biome.key].append(
                    _long_wall_runs(store.get_chunk(cx, cy).tiles.tolist())
                )
    if not all(runs.get(k) for k in ("crystal", "caves", "halls")):
        pytest.skip(f"seed {seed}: not all three biomes within range")
    assert (
        statistics.median(runs["caves"])
        < statistics.median(runs["crystal"])
        < statistics.median(runs["halls"])
    )


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_liquids_appear_in_the_biomes_that_have_them(seed):
    """Statistical and seeded: a water or lava biome does grow pools."""
    from world.biomes import biome_at

    store = _store(seed)
    wet_biomes_seen = set()
    liquid_found = set()
    for cx in range(-8, 9):
        for cy in range(-8, 9):
            biome = biome_at(seed, cx, cy, DEFAULT_CONFIG)
            if biome.liquids == "none":
                continue
            wet_biomes_seen.add(biome.key)
            tiles = store.get_chunk(cx, cy).tiles
            if ((tiles == WATER) | (tiles == LAVA)).any():
                liquid_found.add(biome.key)
    assert wet_biomes_seen, f"seed {seed}: no liquid biomes in range"
    assert liquid_found, f"seed {seed}: liquid biomes {wet_biomes_seen} grew no pools"


@pytest.mark.parametrize("seed", (4242, 7, 99))
def test_a_dry_biome_stays_dry(seed):
    from world.biomes import biome_at

    store = _store(seed)
    for cx in range(-6, 7):
        for cy in range(-6, 7):
            biome = biome_at(seed, cx, cy, DEFAULT_CONFIG)
            if biome.liquids != "none":
                continue
            tiles = store.get_chunk(cx, cy).tiles
            assert not ((tiles == WATER) | (tiles == LAVA)).any(), (
                f"{biome.key} at {(cx, cy)} should have no pools"
            )


# -------------------------------------------------------------- liquids


@pytest.mark.parametrize("seed", (4242, 7))
def test_liquids_are_impassable_and_never_seal_connectivity(seed):
    store = _store(seed)
    checked = 0
    for cx, cy in CAVERNS:
        tiles = store.get_chunk(cx, cy).tiles
        if not ((tiles == WATER) | (tiles == LAVA)).any():
            continue
        checked += 1
        grid = tiles.tolist()
        assert grid[MID][MID] == FLOOR  # center anchor stays walkable
        floors = {
            (x, y)
            for y, row in enumerate(grid)
            for x, tile in enumerate(row)
            if tile == FLOOR
        }
        assert _flood(grid, (MID, MID)) == floors
    assert checked, "expected at least one liquid chunk in the sample"


# ------------------------------------------------------------ streaming


def test_spawn_is_deterministic_and_passable():
    first, second = _store(4242), _store(4242)
    assert first.spawn == second.spawn
    assert first.spawn == (MID, MID)  # chunk (0, 0) center is carved FLOOR
    assert first.tile_at(*first.spawn).passable


def test_tile_at_maps_global_coords_including_negatives():
    store = _store(4242)
    assert store.tile_at(MID, MID) is Tile(store.get_chunk(0, 0).tiles[MID, MID].item())
    assert store.tile_at(-1, -1) is Tile(store.get_chunk(-1, -1).tiles[SIZE - 1, SIZE - 1].item())
    assert store.tile_at(SIZE, -SIZE) is Tile(store.get_chunk(1, -1).tiles[0, 0].item())
    assert store.tile_at(-SIZE - 5, 3 * SIZE + 2) is Tile(
        store.get_chunk(-2, 3).tiles[SIZE - 5, 2].item()
    )


def test_ensure_loaded_generates_the_preload_radius():
    store = _store(4242)
    assert len(store) == 0
    store.ensure_loaded((MID, MID))
    radius = DEFAULT_CONFIG.preload_radius
    expected = {
        (dx, dy)
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
    }
    assert expected <= set(store._chunks.keys())
    assert len(store) == len(expected)
    assert (radius + 1, 0) not in store._chunks  # nothing beyond the radius


def test_ensure_loaded_streams_as_the_agent_moves():
    store = _store(4242)
    store.ensure_loaded((MID, MID))
    before = len(store)
    store.ensure_loaded((MID + 3 * SIZE, MID))  # three chunks east
    assert len(store) > before
    assert (5, 0) in store._chunks


def test_chunks_are_never_discarded():
    store = _store(4242)
    first = store.get_chunk(0, 0)
    for cx in range(-4, 5):
        store.ensure_loaded((cx * SIZE + MID, MID))
    assert store.get_chunk(0, 0) is first  # same object, persistent world


def _first_monster(store, cx, cy):
    chunk = store.get_chunk(cx, cy)
    return chunk.contents.monsters[0] if chunk.contents.monsters else None


def test_a_monster_walking_over_a_chunk_edge_changes_owner():
    """The migration trap: the chunk it left must stop finding it, and the
    chunk it entered must start."""
    store = ChunkStore(DEFAULT_CONFIG, world_seed=21)
    size = DEFAULT_CONFIG.chunk_size
    monster = None
    for cx in range(6):  # find any chunk that actually holds a monster
        monster = _first_monster(store, cx, 0)
        if monster is not None:
            break
    assert monster is not None
    source_key = store.chunk_coords(monster.x, monster.y)
    destination_key = (source_key[0] + 1, source_key[1])
    landing = (destination_key[0] * size + 3, monster.y)

    store.move_entity(monster, *landing)

    assert store.entity_at(*landing) is monster
    assert store.chunk_coords(monster.x, monster.y) == destination_key
    assert monster in store.get_chunk(*destination_key).contents.monsters
    assert monster not in store.get_chunk(*source_key).contents.monsters
    assert store.get_chunk(*source_key).contents.entity_at(*landing) is None


def test_moving_inside_one_chunk_keeps_the_lookup_honest():
    """The index is rebuilt on demand — a move must not leave a stale entry."""
    store = ChunkStore(DEFAULT_CONFIG, world_seed=21)
    monster = None
    for cx in range(6):
        monster = _first_monster(store, cx, 0)
        if monster is not None:
            break
    assert monster is not None
    was = (monster.x, monster.y)
    store.entity_at(*was)  # force the index to be built before the move
    store.move_entity(monster, was[0], was[1] + 1)
    assert store.entity_at(*was) is None
    assert store.entity_at(was[0], was[1] + 1) is monster


def test_removing_a_monster_takes_it_out_of_the_lookup():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=21)
    monster = None
    for cx in range(6):
        monster = _first_monster(store, cx, 0)
        if monster is not None:
            break
    assert monster is not None
    where = (monster.x, monster.y)
    store.entity_at(*where)
    store.remove_entity(monster)
    assert store.entity_at(*where) is None


def _clear_chunk(store, cx, cy):
    contents = store.get_chunk(cx, cy).contents
    contents.monsters.clear()
    contents.invalidate()
    return contents


def test_a_cleared_chunk_refills_when_the_agent_is_far_away():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    contents = _clear_chunk(store, 3, 3)
    store.respawn_pass((0, 0), tick=5000, config=DEFAULT_CONFIG)
    assert len(contents.monsters) == 1  # one at a time, not a full reset


def test_nothing_respawns_next_to_the_agent():
    """Monsters must not materialise in front of someone standing there."""
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    size = DEFAULT_CONFIG.chunk_size
    contents = _clear_chunk(store, 3, 3)
    here = (3 * size + size // 2, 3 * size + size // 2)
    store.respawn_pass(here, tick=5000, config=DEFAULT_CONFIG)
    assert contents.monsters == []


def test_the_respawn_cooldown_paces_the_refill():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    contents = _clear_chunk(store, 3, 3)
    store.respawn_pass((0, 0), tick=5000, config=DEFAULT_CONFIG)
    store.respawn_pass((0, 0), tick=5001, config=DEFAULT_CONFIG)
    assert len(contents.monsters) == 1  # too soon for a second
    later = 5000 + DEFAULT_CONFIG.respawn_cooldown_ticks + 1
    store.respawn_pass((0, 0), tick=later, config=DEFAULT_CONFIG)
    assert len(contents.monsters) == 2


def test_respawn_stops_at_the_per_chunk_cap():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    contents = _clear_chunk(store, 3, 3)
    tick_at = 5000
    for _ in range(DEFAULT_CONFIG.respawn_cap_per_chunk + 6):
        store.respawn_pass((0, 0), tick=tick_at, config=DEFAULT_CONFIG)
        tick_at += DEFAULT_CONFIG.respawn_cooldown_ticks + 1
    assert len(contents.monsters) == DEFAULT_CONFIG.respawn_cap_per_chunk


def test_respawn_never_generates_a_chunk_just_to_fill_it():
    """Repopulating an ungenerated chunk would defeat lazy streaming."""
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    store.get_chunk(0, 0)
    before = len(store)
    store.respawn_pass((0, 0), tick=9999, config=DEFAULT_CONFIG)
    assert len(store) == before


def test_respawned_monsters_land_on_floor_and_never_stack():
    store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
    size = DEFAULT_CONFIG.chunk_size
    contents = _clear_chunk(store, 3, 3)
    tick_at = 5000
    for _ in range(8):
        store.respawn_pass((0, 0), tick=tick_at, config=DEFAULT_CONFIG)
        tick_at += DEFAULT_CONFIG.respawn_cooldown_ticks + 1
    chunk = store.get_chunk(3, 3)
    spots = [(m.x, m.y) for m in contents.monsters]
    assert len(spots) == len(set(spots))
    for x, y in spots:
        assert chunk.tiles[y - 3 * size, x - 3 * size] == int(Tile.FLOOR)


def test_respawn_is_deterministic_for_a_seed():
    def run():
        store = ChunkStore(DEFAULT_CONFIG, world_seed=31)
        contents = _clear_chunk(store, 3, 3)
        store.respawn_pass((0, 0), tick=5000, config=DEFAULT_CONFIG)
        return [(m.kind.key, m.x, m.y) for m in contents.monsters]

    assert run() == run()
