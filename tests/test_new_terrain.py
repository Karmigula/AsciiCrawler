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


# --- the planner's model of ice, and the physics it has to match ---


def _random_ice_field(rng, size=9):
    """A patch of floor, ice and rock, with a floor tile to start from."""
    weights = [Tile.FLOOR, Tile.FLOOR, Tile.ICE, Tile.ICE, Tile.ICE, Tile.WALL]
    field = {
        (x, y): weights[rng.randrange(len(weights))]
        for x in range(size)
        for y in range(size)
    }
    field[(size // 2, size // 2)] = Tile.FLOOR
    return field


def test_the_planners_slide_prediction_matches_the_physics():
    """Two implementations of one rule; the whole design rests on them agreeing.

    `slide_landing` exists so a plan can say where a step really ends, and
    `_slide` is what actually happens. If they ever disagree the agent plans
    routes it cannot walk, so this walks a few hundred random steps over
    random ice and demands the prediction land on the same tile every time.

    Belief is loaded with the whole truth here on purpose: the two must agree
    given the same information. Where the agent's memory is *wrong* the
    prediction is allowed to be wrong with it, and re-planning sorts it out.
    """
    import random
    from dataclasses import replace

    from agent.memory import Memory
    from agent.pathing import slide_landing
    from agent.stats import Stats
    from sim.tick import AgentState, MOVED, _try_step

    rng = random.Random(20260910)
    config = replace(DEFAULT_CONFIG, ice_slide_max=3)
    checked = 0
    for _ in range(120):
        field = _random_ice_field(rng)
        memory = Memory()
        memory.observe(dict(field), tick=0)
        world = TerrainWorld(field)
        centre = (4, 4)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            agent = AgentState(x=centre[0], y=centre[1])
            agent.stats = Stats.starting(config)
            agent.derived = _bundle(agent.stats)
            entry = (centre[0] + dx, centre[1] + dy)
            if _try_step(agent, entry, world, random.Random(1), config) != MOVED:
                continue
            predicted = slide_landing(memory, entry, (dx, dy), config.ice_slide_max)
            assert predicted == (agent.x, agent.y), (
                f"stepping {(dx, dy)} onto {entry}: planned {predicted}, "
                f"physics landed {(agent.x, agent.y)}"
            )
            checked += 1
    assert checked > 200, f"only {checked} legal steps exercised; test proves little"


def test_a_plan_across_ice_is_still_a_run_of_single_steps():
    """Search hops over a slide; everything downstream reads adjacent cells."""
    from agent.pathing import _fill_slides

    path = _fill_slides((0, 0), [(4, 0), (4, 3), (2, 5)])

    assert path[-1] == (2, 5), "the destination survives the expansion"
    here = (0, 0)
    for step in path:
        assert max(abs(step[0] - here[0]), abs(step[1] - here[1])) == 1, (
            f"{here} -> {step} is not a single step"
        )
        here = step


def test_a_slide_advances_the_plan_past_every_tile_it_crossed():
    """One tick can cover four tiles; popping one entry leaves the plan behind.

    Before the plan advanced by landing tile, a slide desynced it by its own
    length: the next entry was several tiles away, physics refused it as a
    non-step, and the plan was thrown away and rebuilt every time the agent
    touched ice.
    """
    from agent.goals import ExploreGoal
    from sim.tick import _advance_plan

    driver = ExploreGoal()
    driver.path = [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]

    _advance_plan(driver, (3, 0))

    assert driver.path == [(4, 0), (5, 0)], "the crossed tiles should be gone"


def test_a_slide_that_ran_short_leaves_the_plan_pointing_at_the_right_place():
    """A body in the way stops a slide early; the plan must survive that."""
    from agent.goals import ExploreGoal
    from sim.tick import _advance_plan

    driver = ExploreGoal()
    driver.path = [(1, 0), (2, 0), (3, 0), (4, 0)]

    _advance_plan(driver, (1, 0))  # slid nowhere at all

    assert driver.path == [(2, 0), (3, 0), (4, 0)]


def test_an_aware_planner_uses_a_frozen_hall_as_fast_travel():
    """Ice crosses several tiles per tick, so it is quick, not merely awkward.

    The unaware planner priced ice purely as a penalty and crept along the
    rock beside it. Since a slide is one tick however far it carries, the
    frozen lane is the faster way and the plan should take it.
    """
    import random
    from dataclasses import replace

    from agent.memory import Memory
    from agent.pathing import StepCosts, astar

    seen = {}
    for x in range(12):
        seen[(x, 0)] = Tile.ICE  # the frozen hall
        seen[(x, 2)] = Tile.FLOOR  # bare rock, same length
    seen[(0, 1)] = seen[(11, 1)] = Tile.FLOOR
    memory = Memory()
    memory.observe(seen, tick=0)

    config = replace(DEFAULT_CONFIG, ice_slide_max=3, model_ice_slides=True)
    costs = StepCosts.from_config(config)
    plan = astar(memory, (0, 1), (11, 1), costs=costs)

    assert plan is not None
    on_ice = sum(1 for step in plan if memory.terrain(step) is Tile.ICE)
    assert on_ice > 0, "the frozen lane is the fast one; the plan ignored it"
    # The plan lists tiles, and a slide crosses several of them per tick, so
    # its length measures distance rather than time. What says the planner
    # understood the ice is that it left the rock lane alone.
    assert not any(memory.terrain(step) is Tile.FLOOR and step[1] == 2 for step in plan), (
        f"the plan crept along the rock instead of sliding: {plan}"
    )


def test_a_plan_survives_a_landing_it_did_not_predict():
    """An overshot route still mostly goes somewhere worth going.

    Clearing the plan whenever the landing was a surprise reads as the tidy
    thing to do and measured worse: 493 tiles from spawn across sixteen worlds
    against 526 for keeping it. If the agent ended up anywhere along the
    route, the rest of the route still leads where it was headed.
    """
    from agent.goals import ExploreGoal
    from sim.tick import _advance_plan

    driver = ExploreGoal()
    driver.path = [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0)]

    _advance_plan(driver, (5, 0))  # slid far past the tile it aimed at

    assert driver.path == [(6, 0)], "the plan should resume from the landing"


def test_a_frontier_tile_stranded_mid_drift_is_still_worth_going_to():
    """A slide crosses it, so the agent sees it - which is all exploring is.

    Nothing can stop in the middle of a drift, so these tiles were absent from
    every sweep and the explorer called the whole neighbourhood unreachable
    and went back to wandering: 652 starved ticks across eight worlds.
    """
    from dataclasses import replace

    from agent.memory import Memory
    from agent.pathing import StepCosts, distances

    lane = {(x, 0): Tile.ICE for x in range(1, 6)}
    lane[(0, 0)] = Tile.FLOOR
    memory = Memory()
    memory.observe(lane, tick=0)

    config = replace(DEFAULT_CONFIG, ice_slide_max=3, model_ice_slides=True)
    cost, came_from = distances(
        memory, (0, 0), costs=StepCosts.from_config(config)
    )

    assert (2, 0) in cost, "a tile the slide passes over should be reachable"
    assert (2, 0) in came_from, "and it should be plannable to"


class LootWorld(TerrainWorld):
    """A terrain strip that also has things lying on it."""

    def __init__(self, row, items=None):
        super().__init__(row)
        self.items = dict(items or {})
        self.taken = []

    def item_at(self, x, y):
        return self.items.get((x, y))

    def take_item(self, x, y):
        item = self.items.pop((x, y), None)
        if item is not None:
            self.taken.append((x, y))
        return item


def test_loot_on_the_ice_is_picked_up_on_the_way_past():
    """An adventure could be softlocked by an amulet lying on a drift.

    Picking up read only the tile the agent finished on, and a slide finishes
    somewhere further along - so the agent planned onto the loot, the ice took
    it past, and it planned onto the loot again. One run spent sixteen
    thousand ticks doing that with 166 tiles explored.
    """
    from dataclasses import replace

    from agent.stats import Stats
    from sim.items import ITEMS
    from sim.tick import AgentState, MOVED, _try_step

    config = replace(DEFAULT_CONFIG, ice_slide_max=3)
    row = _floor_strip()
    for x in range(3, 9):
        row[(x, 0)] = Tile.ICE
    kind = next(item for item in ITEMS if item.key == "gold")
    prize = type("Lying", (), {"kind": kind, "x": 5, "y": 0})()
    world = LootWorld(row, {(5, 0): prize})

    agent = AgentState(x=2, y=0)
    agent.stats = Stats.starting(config)
    agent.derived = _bundle(agent.stats)

    assert _try_step(agent, (3, 0), world, random.Random(1), config) == MOVED
    from sim.tick import _pick_up

    _pick_up(agent, world, config)

    assert agent.x > 5, "the slide should have carried it past the loot"
    assert (5, 0) in world.taken, "it slid straight over the loot and left it"
