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
