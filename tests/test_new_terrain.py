"""The awkward tiles and the built generators."""

import random
from dataclasses import replace

import pytest

from config import DEFAULT_CONFIG
from world import gen_causeway, gen_lattice, gen_maze, gen_scatter, gen_station
from world.biomes import BIOMES, BY_KEY
from world.tiles import Tile

SIZE = 48


def _bundle(stats, config=DEFAULT_CONFIG):
    from agent.loadout import derive

    return derive(stats, {}, config)


def _grid(module, *args):
    return module.generate(random.Random(5), SIZE, SIZE, *args)


BUILT = (
    (gen_station, (11, 0.62, 0.16)),
    (gen_maze, (0.3,)),
    (gen_causeway, (3, 0.65)),
    (gen_lattice, (6, 0.3)),
)


@pytest.mark.parametrize("module, args", BUILT)
def test_a_generator_is_deterministic(module, args):
    assert _grid(module, *args).tobytes() == _grid(module, *args).tobytes()


@pytest.mark.parametrize("module, args", BUILT)
def test_a_generator_walls_its_border(module, args):
    """The chunk pipeline drills its own seams; a generator that leaves the
    edge open would let a room spill into the next chunk."""
    grid = _grid(module, *args).tolist()
    wall = int(Tile.WALL)
    assert all(v == wall for v in grid[0])
    assert all(v == wall for v in grid[-1])
    assert all(row[0] == wall and row[-1] == wall for row in grid)


@pytest.mark.parametrize("module, args", BUILT)
def test_a_generator_leaves_somewhere_to_stand(module, args):
    grid = _grid(module, *args)
    assert (grid == int(Tile.FLOOR)).sum() > SIZE, "a chunk with no floor is not a place"


def test_the_maze_is_mostly_wall_and_the_lattice_mostly_floor():
    """They are opposite problems: everything walkable and nothing direct,
    against almost nothing walkable and what remains running straight."""
    maze = _grid(gen_maze, 0.3)
    lattice = _grid(gen_lattice, 6, 0.3)
    floor = int(Tile.FLOOR)
    assert (maze == floor).mean() < 0.6
    assert (lattice == floor).mean() > 0.6


def test_the_cathedral_is_mostly_water():
    grid = _grid(gen_causeway, 3, 0.65)
    assert (grid == int(Tile.WATER)).mean() > 0.5


def test_the_station_has_straight_walls():
    """It was built, not eroded."""
    grid = _grid(gen_station, 11, 0.62, 0.16).tolist()
    wall = int(Tile.WALL)
    longest = 0
    for row in grid:
        run = 0
        for value in row:
            run = run + 1 if value == wall else 0
            longest = max(longest, run)
    assert longest >= 8


def test_scatter_only_touches_floor():
    """A drift must never seal a pool or eat the structure it settled on."""
    import numpy as np

    tiles = np.full((20, 20), int(Tile.WALL), dtype=np.int8)
    tiles[5:15, 5:15] = int(Tile.FLOOR)
    tiles[6, 6] = int(Tile.WATER)
    gen_scatter.scatter(tiles, random.Random(1), int(Tile.ICE), 0.9, 1, 5)
    assert tiles[0, 0] == int(Tile.WALL)
    assert tiles[6, 6] == int(Tile.WATER)
    assert (tiles == int(Tile.ICE)).any()


def test_scatter_of_zero_chance_changes_nothing():
    import numpy as np

    tiles = np.full((10, 10), int(Tile.FLOOR), dtype=np.int8)
    before = tiles.tobytes()
    gen_scatter.scatter(tiles, random.Random(1), int(Tile.ICE), 0.0, 1, 5)
    assert tiles.tobytes() == before


def test_every_biome_names_a_builder_that_exists():
    from world.chunks import _BUILDERS

    for biome in BIOMES:
        assert biome.builder in _BUILDERS, biome.key


def test_every_biome_has_a_palette_for_the_tiles_it_can_contain():
    for biome in BIOMES:
        palette = DEFAULT_CONFIG.biome_colors[biome.key]
        assert "#" in palette and "." in palette
        if biome.has_water:
            assert "~" in palette
        if biome.has_lava:
            assert "^" in palette
        scatter = biome.params.get("scatter")
        if scatter:
            assert Tile[scatter["tile"]].glyph in palette, biome.key


def test_biome_keys_are_unique():
    keys = [biome.key for biome in BIOMES]
    assert len(set(keys)) == len(keys)
    assert len(BY_KEY) == len(BIOMES)


def test_every_biome_can_actually_be_rolled():
    """A weight of zero would make a place that exists only in the table."""
    for biome in BIOMES:
        assert biome.weight > 0, biome.key


# ---------------------------------------------------------- ice and haze


class TerrainWorld:
    """A strip of chosen tiles, for testing what walking on them costs."""

    def __init__(self, row: dict, monsters=()):
        self.row = row
        self.monsters = list(monsters)

    def tile_at(self, x, y):
        return self.row.get((x, y), Tile.WALL)

    def ensure_loaded(self, position):
        pass

    def entity_at(self, x, y):
        for monster in self.monsters:
            if (monster.x, monster.y) == (x, y):
                return monster
        return None


def _floor_strip(length=20, y=0, tile=Tile.FLOOR):
    return {(x, y): tile for x in range(length)}


def test_ice_carries_the_agent_on():
    from agent.stats import Stats
    from sim.tick import AgentState, _try_step

    row = _floor_strip()
    for x in range(3, 9):
        row[(x, 0)] = Tile.ICE
    agent = AgentState(x=2, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.derived = _bundle(agent.stats)

    _try_step(agent, (3, 0), TerrainWorld(row), random.Random(1), DEFAULT_CONFIG)

    assert agent.x > 3, "it should not stop where it stepped"
    assert agent.x <= 3 + DEFAULT_CONFIG.ice_slide_max, "and not slide forever"


def test_a_slide_stops_at_a_wall():
    """What is under test is where a slide ends, not how long slides are.

    This asked for a three-tile slide by reading the shipped default, so
    retuning that default failed a test about walls. The run length is now
    stated here: the ice is as long as the slide allowed, and the assertion is
    that the agent stops on the last of it rather than through the rock.
    """
    from dataclasses import replace

    from agent.stats import Stats
    from sim.tick import AgentState, _try_step

    config = replace(DEFAULT_CONFIG, ice_slide_max=3)
    row = {(x, 0): Tile.ICE for x in range(2, 5)}
    row[(1, 0)] = Tile.FLOOR
    agent = AgentState(x=1, y=0)
    agent.stats = Stats.starting(config)
    agent.derived = _bundle(agent.stats)

    _try_step(agent, (2, 0), TerrainWorld(row), random.Random(1), config)

    assert agent.x == 4, "slides to the end of the ice and stops at the rock"


def test_a_slide_stops_against_a_monster():
    from agent.stats import Stats
    from sim.monsters import MONSTERS
    from sim.tick import AgentState, _try_step
    from world.populate import Monster

    kind = next(k for k in MONSTERS if k.glyph == "g")
    blocker = Monster(kind=kind, x=4, y=0, hp=kind.hp)
    row = {(x, 0): Tile.ICE for x in range(2, 8)}
    row[(1, 0)] = Tile.FLOOR
    agent = AgentState(x=1, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.derived = _bundle(agent.stats)

    _try_step(agent, (2, 0), TerrainWorld(row, [blocker]), random.Random(1), DEFAULT_CONFIG)

    assert agent.x == 3, "stopped by what it slid into"


def test_ordinary_floor_does_not_slide():
    from agent.stats import Stats
    from sim.tick import AgentState, _try_step

    agent = AgentState(x=1, y=0)
    agent.stats = Stats.starting(DEFAULT_CONFIG)
    agent.derived = _bundle(agent.stats)
    _try_step(agent, (2, 0), TerrainWorld(_floor_strip()), random.Random(1), DEFAULT_CONFIG)
    assert agent.x == 2


def test_standing_in_haze_hurts():
    from sim.tick import AgentState, tick

    row = _floor_strip(tile=Tile.HAZE)
    agent = AgentState(x=5, y=0)
    tick(agent, TerrainWorld(row), random.Random(1), DEFAULT_CONFIG)
    assert agent.stats.hp == agent.stats.max_hp - DEFAULT_CONFIG.haze_damage
    assert agent.last_wound == "the spores"


def test_clear_air_does_not_hurt():
    from sim.tick import AgentState, tick

    agent = AgentState(x=5, y=0)
    tick(agent, TerrainWorld(_floor_strip()), random.Random(1), DEFAULT_CONFIG)
    assert agent.stats.hp == agent.stats.max_hp


def test_a_plan_goes_around_fog_when_going_around_is_cheap():
    from agent.memory import Memory
    from agent.pathing import astar

    memory = Memory()
    observation = {(x, y): Tile.FLOOR for x in range(6) for y in range(3)}
    for y in range(3):
        observation[(3, 1)] = Tile.HAZE
    memory.observe(observation, tick=1)

    path = astar(memory, (0, 1), (5, 1))

    assert path is not None
    assert (3, 1) not in path, "there was clear air either side"


def test_a_plan_crosses_fog_when_that_is_the_only_way():
    from agent.memory import Memory
    from agent.pathing import astar

    memory = Memory()
    observation = {(x, 1): Tile.FLOOR for x in range(6)}
    observation.update({(x, y): Tile.WALL for x in range(6) for y in (0, 2)})
    observation[(3, 1)] = Tile.HAZE
    memory.observe(observation, tick=1)

    path = astar(memory, (0, 1), (5, 1))

    assert path is not None, "fog is passable, just unpleasant"
    assert (3, 1) in path
