"""Population: deterministic per chunk, and deeper the further out you go."""

import random
from dataclasses import replace

import numpy as np
import pytest

from config import DEFAULT_CONFIG
from sim.monsters import MAX_TIER
from world.chunks import ChunkStore
from world.populate import ChunkContents, depth_fraction, max_tier_for, populate
from world.tiles import Tile

FLOOR = int(Tile.FLOOR)


def _open_chunk() -> np.ndarray:
    size = DEFAULT_CONFIG.chunk_size
    return np.full((size, size), FLOOR, dtype=np.int8)


def _roll(seed: int, cx: int, cy: int, tiles=None) -> ChunkContents:
    return populate(
        random.Random(seed), _open_chunk() if tiles is None else tiles, cx, cy, DEFAULT_CONFIG
    )


def _places(contents: ChunkContents) -> list[tuple]:
    return (
        [(m.kind.key, m.x, m.y, m.hp) for m in contents.monsters]
        + [(i.kind.key, i.x, i.y) for i in contents.items]
        + [(t.x, t.y, t.hidden) for t in contents.traps]
    )


@pytest.mark.parametrize("cx, cy", [(0, 0), (3, -2), (-5, -7), (11, 4)])
def test_same_seed_and_coords_populate_identically(cx, cy):
    assert _places(_roll(9, cx, cy)) == _places(_roll(9, cx, cy))


def test_the_world_seed_reaches_population_through_the_chunk_store():
    """Two stores on one seed agree; a different seed rolls differently."""
    same = [ChunkStore(DEFAULT_CONFIG, world_seed=5).get_chunk(2, -3) for _ in range(2)]
    assert _places(same[0].contents) == _places(same[1].contents)
    other = ChunkStore(DEFAULT_CONFIG, world_seed=6).get_chunk(2, -3)
    assert _places(other.contents) != _places(same[0].contents)


def test_nothing_spawns_on_a_wall_or_a_liquid():
    """Spawns land on ground that can be walked on.

    This asked for FLOOR exactly, which was the same thing until ice and fog
    arrived - both walkable, both scattered across whole biomes. Asserting the
    tile rather than the property meant the test agreed with a bug that left a
    sixth of those chunks empty. What it is really protecting against is a
    monster in lava, unreachable forever, and that is what it now says.
    """
    store = ChunkStore(DEFAULT_CONFIG, world_seed=3)
    size = DEFAULT_CONFIG.chunk_size
    for cx, cy in ((0, 0), (4, 4), (-9, 6)):
        chunk = store.get_chunk(cx, cy)
        for x, y in (
            [(m.x, m.y) for m in chunk.contents.monsters]
            + [(i.x, i.y) for i in chunk.contents.items]
            + [(t.x, t.y) for t in chunk.contents.traps]
        ):
            tile = Tile(int(chunk.tiles[y - cy * size, x - cx * size]))
            assert tile.passable, f"something spawned on {tile.name}"


def test_nothing_spawns_on_the_chunk_centre():
    """The centre is the pipeline's carve anchor and the agent's spawn tile."""
    size = DEFAULT_CONFIG.chunk_size
    centre = (size // 2, size // 2)
    contents = _roll(1, 0, 0)
    occupied = {(m.x, m.y) for m in contents.monsters}
    occupied |= {(i.x, i.y) for i in contents.items}
    occupied |= {(t.x, t.y) for t in contents.traps}
    assert centre not in occupied


def test_spawns_never_share_a_tile():
    contents = _roll(4, 6, 6)
    spots = (
        [(m.x, m.y) for m in contents.monsters]
        + [(i.x, i.y) for i in contents.items]
        + [(t.x, t.y) for t in contents.traps]
    )
    assert len(spots) == len(set(spots))


def test_monster_density_rises_with_distance_from_spawn():
    """Statistical over seeds: far chunks are more crowded than near ones."""
    near = sum(len(_roll(s, 0, 0).monsters) for s in range(8))
    mid = sum(len(_roll(s, 6, 0).monsters) for s in range(8))
    far = sum(len(_roll(s, 18, 0).monsters) for s in range(8))
    assert near < mid < far


def test_monster_tier_rises_with_distance_from_spawn():
    def mean_tier(cx: int) -> float:
        tiers = [m.kind.tier for s in range(8) for m in _roll(s, cx, 0).monsters]
        return sum(tiers) / len(tiers)

    assert mean_tier(0) < mean_tier(7) < mean_tier(20)


def test_the_shallowest_chunks_only_hold_the_shallowest_table():
    assert max_tier_for(0, 0, DEFAULT_CONFIG) == 0
    assert all(m.kind.tier == 0 for s in range(8) for m in _roll(s, 0, 0).monsters)


def test_depth_saturates_at_tier_distance_max():
    cfg = DEFAULT_CONFIG
    beyond = cfg.tier_distance_max * 4 // cfg.chunk_size
    assert depth_fraction(beyond, 0, cfg) == 1.0
    assert max_tier_for(beyond, 0, cfg) == MAX_TIER


def test_monster_hp_starts_at_its_kind_maximum():
    assert all(m.hp == m.kind.hp for m in _roll(2, 5, 5).monsters)


def test_traps_are_placed_hidden():
    assert all(trap.hidden for trap in _roll(2, 5, 5).traps)


def test_respawn_ceiling_is_carried_as_data_for_phase_4():
    """The cooldown is data this phase: nothing ticks it, the cap rides along."""
    contents = _roll(2, 5, 5)
    assert contents.respawn_cap == DEFAULT_CONFIG.respawn_cap_per_chunk
    assert contents.respawn_tick == 0


def test_a_chunk_with_no_floor_populates_nothing():
    size = DEFAULT_CONFIG.chunk_size
    solid = np.full((size, size), int(Tile.WALL), dtype=np.int8)
    contents = populate(random.Random(1), solid, 9, 9, DEFAULT_CONFIG)
    assert not contents.monsters and not contents.items and not contents.traps


def test_population_never_disturbs_the_tiles_it_reads():
    tiles = _open_chunk()
    before = tiles.tobytes()
    _roll(3, 2, 2, tiles)
    assert tiles.tobytes() == before


def test_zero_density_config_spawns_nothing():
    cfg = replace(
        DEFAULT_CONFIG,
        spawn_density_near=0.0,
        spawn_density_far=0.0,
        item_density=0.0,
        trap_density=0.0,
    )
    contents = populate(random.Random(1), _open_chunk(), 4, 4, cfg)
    assert not contents.monsters and not contents.items and not contents.traps


def test_a_refilled_chunk_keeps_its_biome_bestiary():
    """A cleared station used to refill with rats.

    `populate` honoured the biome's monsters and `try_respawn` did not, so a
    themed chunk stayed themed exactly until the agent had killed what was in
    it - and the theme was strongest in the places worth walking to.
    """
    import random

    from config import DEFAULT_CONFIG
    from world.chunks import ChunkStore

    store = ChunkStore(DEFAULT_CONFIG, world_seed=3)
    themed = None
    for cx in range(-8, 9):
        for cy in range(-8, 9):
            biome = store.biome_of(cx, cy)
            if biome.monsters:
                themed = (cx, cy, biome)
                break
        if themed:
            break
    assert themed, "no biome in range declares its own bestiary"
    cx, cy, biome = themed

    chunk = store.get_chunk(cx, cy)
    chunk.contents.monsters.clear()
    chunk.contents.respawn_tick = 0
    from world.populate import try_respawn

    spawned = []
    for tick in range(0, 400):
        chunk.contents.respawn_tick = 0
        monster = try_respawn(
            random.Random(tick),
            chunk.tiles,
            cx,
            cy,
            chunk.contents,
            DEFAULT_CONFIG,
            tick,
            allowed=biome.monsters,
        )
        if monster:
            spawned.append(monster.kind.glyph)
        if len(spawned) > 25:
            break

    assert spawned, "nothing respawned; the test proves nothing"
    assert set(spawned) <= set(biome.monsters), (
        f"{biome.key} respawned {set(spawned) - set(biome.monsters)}"
    )


def test_spawns_use_every_walkable_tile_not_just_bare_floor():
    """Ice and fog are walked on, so things belong on them.

    Spelling the rule as FLOOR quietly thinned the biomes that scatter other
    passable ground: a sixth of a spore chunk was ineligible for anything.
    """
    import random

    import numpy as np

    from config import DEFAULT_CONFIG
    from world.populate import populate
    from world.tiles import Tile

    size = DEFAULT_CONFIG.chunk_size
    tiles = np.full((size, size), int(Tile.WALL), dtype=np.int8)
    # A room of nothing but ice and fog, with no bare floor anywhere.
    tiles[2 : size - 2, 2 : size - 2] = int(Tile.ICE)
    tiles[2 : size // 2, 2 : size - 2] = int(Tile.HAZE)

    contents = populate(random.Random(5), tiles, 6, 6, DEFAULT_CONFIG)

    assert contents.monsters or contents.items, (
        "a chunk of walkable ice and fog spawned nothing at all"
    )
