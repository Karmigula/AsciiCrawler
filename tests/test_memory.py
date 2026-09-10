import pytest

from agent.memory import Memory
from world.tiles import Tile


def test_observe_records_only_the_tiles_handed_in():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR, (3, 7): Tile.WALL}, tick=5)
    assert set(memory.known()) == {(0, 0), (3, 7)}


def test_observe_stores_terrain_belief_and_tick():
    memory = Memory()
    memory.observe({(2, 2): Tile.WALL}, tick=11)
    assert memory.terrain((2, 2)) is Tile.WALL
    assert memory.age((2, 2), 11) == 0


def test_observe_returns_count_of_new_tiles():
    memory = Memory()
    first = memory.observe({(0, 0): Tile.FLOOR, (1, 0): Tile.FLOOR}, tick=1)
    second = memory.observe({(0, 0): Tile.FLOOR, (2, 0): Tile.WALL}, tick=2)
    assert first == 2
    assert second == 1


def test_believes_passable_for_floor_wall_and_unknown():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR, (1, 0): Tile.WALL}, tick=1)
    assert memory.believes_passable((0, 0))
    assert not memory.believes_passable((1, 0))
    assert not memory.believes_passable((99, 99))


def test_age_grows_with_ticks():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=3)
    assert memory.age((0, 0), 3) == 0
    assert memory.age((0, 0), 4) == 1
    assert memory.age((0, 0), 10) == 7


def test_re_sighting_refreshes_age_without_new_records():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=1)
    assert memory.observe({(0, 0): Tile.FLOOR}, tick=9) == 0
    assert len(memory) == 1
    assert memory.age((0, 0), 9) == 0


def test_age_of_never_seen_tile_raises():
    memory = Memory()
    with pytest.raises(KeyError):
        memory.age((5, 5), 10)


def test_generation_bumps_only_on_new_tiles():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=1)
    bump = memory.generation
    memory.observe({(0, 0): Tile.FLOOR}, tick=2)
    assert memory.generation == bump
    memory.observe({(1, 1): Tile.FLOOR}, tick=3)
    assert memory.generation == bump + 1


def test_prune_drops_expired_records_and_keeps_the_rest():
    """The pruner is what bounds the dict by recent, not lifetime, experience."""
    memory = Memory()
    memory.observe({(x, 0): Tile.FLOOR for x in range(100)}, tick=1)
    memory.observe({(x, 1): Tile.FLOOR for x in range(40)}, tick=900)
    dropped = memory.prune(tick=1000, ttl=500)
    assert dropped == 100
    assert len(memory) == 40
    assert (0, 0) not in memory
    assert (0, 1) in memory


def test_prune_expires_on_age_strictly_greater_than_ttl():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=0)
    assert memory.prune(tick=500, ttl=500) == 0  # exactly at the TTL: still known
    assert memory.prune(tick=501, ttl=500) == 1


def test_prune_bumps_the_generation_so_the_brain_re_looks():
    """Forgetting changes the frontier as much as discovering does."""
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=0)
    before = memory.generation
    memory.prune(tick=10_000, ttl=100)
    assert memory.generation > before


def test_prune_that_drops_nothing_leaves_the_generation_alone():
    memory = Memory()
    memory.observe({(0, 0): Tile.FLOOR}, tick=0)
    before = memory.generation
    assert memory.prune(tick=10, ttl=100) == 0
    assert memory.generation == before


def test_a_forgotten_tile_becomes_unknown_again():
    """The point of decay: pruned ground is indistinguishable from unseen."""
    memory = Memory()
    memory.observe({(4, 4): Tile.FLOOR}, tick=0)
    memory.prune(tick=10_000, ttl=100)
    assert (4, 4) not in memory
    assert memory.terrain((4, 4)) is None
    assert not memory.believes_passable((4, 4))
    assert list(memory.known()) == []


def test_memory_records_what_was_standing_on_a_tile():
    memory = Memory()
    memory.observe(
        {(1, 1): Tile.FLOOR, (2, 2): Tile.FLOOR},
        tick=5,
        entities={(1, 1): "g"},
        items={(2, 2): "!"},
    )
    assert memory.snapshot((1, 1)) == ("g", None)
    assert memory.snapshot((2, 2)) == (None, "!")


def test_re_sighting_an_empty_tile_clears_its_snapshot():
    """The agent believes what it last saw — including seeing something gone."""
    memory = Memory()
    memory.observe({(1, 1): Tile.FLOOR}, tick=1, entities={(1, 1): "g"})
    memory.observe({(1, 1): Tile.FLOOR}, tick=2)
    assert memory.snapshot((1, 1)) == (None, None)


def test_snapshot_of_an_unknown_tile_is_empty():
    assert Memory().snapshot((9, 9)) == (None, None)


def test_the_entity_index_tracks_what_memory_believes_is_standing_there():
    """The index is maintained, not searched, so it has to stay in step -
    a stale entry is an invisible monster or a phantom one."""
    memory = Memory()
    memory.observe({(1, 1): Tile.FLOOR}, tick=1, entities={(1, 1): "g"})
    assert memory.entity_coords() == {(1, 1)}


def test_seeing_a_tile_empty_takes_it_out_of_the_entity_index():
    memory = Memory()
    memory.observe({(1, 1): Tile.FLOOR}, tick=1, entities={(1, 1): "g"})
    memory.observe({(1, 1): Tile.FLOOR}, tick=2)
    assert memory.entity_coords() == set()


def test_pruning_clears_the_indexes_too():
    """Otherwise a forgotten monster keeps frightening the agent forever."""
    memory = Memory()
    memory.observe(
        {(1, 1): Tile.FLOOR}, tick=1, entities={(1, 1): "D"}, items={(1, 1): "!"}
    )
    memory.prune(tick=10_000, ttl=100)
    assert memory.entity_coords() == set()
    assert memory.item_coords() == set()


def test_the_item_index_tracks_remembered_loot():
    memory = Memory()
    memory.observe({(2, 2): Tile.FLOOR}, tick=1, items={(2, 2): ")"})
    assert memory.item_coords() == {(2, 2)}
    memory.observe({(2, 2): Tile.FLOOR}, tick=2)
    assert memory.item_coords() == set()


def test_the_indexes_agree_with_the_records_they_summarise():
    """The property that makes the index safe to read instead of the records."""
    memory = Memory()
    memory.observe(
        {(x, 0): Tile.FLOOR for x in range(20)},
        tick=1,
        entities={(3, 0): "r", (7, 0): "o"},
        items={(5, 0): "!", (7, 0): ")"},
    )
    memory.observe({(3, 0): Tile.FLOOR}, tick=2)  # the rat moved on
    from_records = {c for c in memory.known() if memory.snapshot(c)[0] is not None}
    assert memory.entity_coords() == from_records
    items_from_records = {c for c in memory.known() if memory.snapshot(c)[1] is not None}
    assert memory.item_coords() == items_from_records


def test_ground_that_was_lit_but_not_seen_keeps_its_snapshots():
    """Lava lights terrain the agent has no line of sight to. Refreshing that
    terrain must not erase the monster it remembers standing there."""
    memory = Memory()
    memory.observe({(5, 5): Tile.FLOOR}, tick=1, entities={(5, 5): "T"})
    assert memory.snapshot((5, 5))[0] == "T"

    # Seen-set excludes (5,5): it is only lit, not observed.
    memory.observe({(5, 5): Tile.FLOOR}, tick=2, snapshot_coords={(9, 9)})

    assert memory.snapshot((5, 5))[0] == "T", "a lit tile must not wipe the sighting"
    assert memory.entity_coords() == {(5, 5)}
    # And light must not reset the decay clock either: a record refreshed every
    # tick never expires, and the monster remembered on it becomes an immortal
    # phantom that can pin the agent in flight for the rest of the run.
    assert memory.age((5, 5), 2) == 1


def test_a_tile_actually_seen_still_clears_its_snapshot():
    memory = Memory()
    memory.observe({(5, 5): Tile.FLOOR}, tick=1, entities={(5, 5): "T"})
    memory.observe({(5, 5): Tile.FLOOR}, tick=2, snapshot_coords={(5, 5)})
    assert memory.snapshot((5, 5))[0] is None


def _brute_force_frontier(memory):
    """The definition, computed the slow way, for the incremental set to match."""
    from agent.memory import _NEIGHBOURS

    found = set()
    for coord in memory.known():
        if not memory.believes_passable(coord):
            continue
        x, y = coord
        if any((x + dx, y + dy) not in memory for dx, dy in _NEIGHBOURS):
            found.add(coord)
    return found


def test_the_maintained_frontier_matches_the_definition():
    """A maintained set can drift where a recomputed one cannot, and a wrong
    frontier sends the agent to places it has already seen - or nowhere."""
    import random

    rng = random.Random(1234)
    memory = Memory()
    tick_at = 0
    for step in range(300):
        tick_at += 1
        # A ragged blob of observations, so tiles arrive with unknown
        # neighbours on every side and in every order.
        cx, cy = rng.randrange(-20, 20), rng.randrange(-20, 20)
        observation = {}
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if rng.random() < 0.7:
                    coord = (cx + dx, cy + dy)
                    observation[coord] = (
                        Tile.FLOOR if rng.random() < 0.75 else Tile.WALL
                    )
        memory.observe(observation, tick=tick_at)
        if step % 25 == 24:
            memory.prune(tick=tick_at, ttl=rng.randrange(1, 30))
        assert memory.frontier() == _brute_force_frontier(memory), f"step {step}"


def test_forgetting_a_tile_puts_its_neighbours_back_on_the_frontier():
    """The case that makes decay recycle novelty at all."""
    memory = Memory()
    memory.observe(
        {(x, y): Tile.FLOOR for x in range(-1, 2) for y in range(-1, 2)}, tick=1
    )
    memory.observe({(0, 0): Tile.FLOOR}, tick=500)  # keep the middle fresh
    assert (0, 0) not in memory.frontier(), "fully surrounded by known ground"

    memory.prune(tick=600, ttl=200)  # the ring expires, the middle survives

    assert (0, 0) in memory.frontier(), "its neighbours are unknown again"
    assert memory.frontier() == _brute_force_frontier(memory)


def test_a_wall_is_never_frontier():
    memory = Memory()
    memory.observe({(0, 0): Tile.WALL}, tick=1)
    assert memory.frontier() == set()


def test_a_tile_walled_in_on_every_side_is_not_frontier():
    memory = Memory()
    observation = {(x, y): Tile.WALL for x in range(-1, 2) for y in range(-1, 2)}
    observation[(0, 0)] = Tile.FLOOR
    memory.observe(observation, tick=1)
    assert (0, 0) not in memory.frontier()
