import random

from config import DEFAULT_CONFIG
from sim.tick import AgentState, tick
from world.tiles import Tile

# ticks to sweep a large open field (measured ~2500 for 96x54; margin on top)
OPEN_FIELD_TICKS = 4000


class FiniteWorld:
    """The old finite-grid world behind the chunk-store interface: tile_at
    answers WALL outside the grid, streaming is a no-op."""

    def __init__(self, tiles: list[list[Tile]]) -> None:
        self.tiles = tiles

    def tile_at(self, x: int, y: int) -> Tile:
        if 0 <= y < len(self.tiles) and 0 <= x < len(self.tiles[0]):
            return self.tiles[y][x]
        return Tile.WALL

    def ensure_loaded(self, position: tuple[int, int]) -> None:
        pass


def _open_field(width: int = 96, height: int = 54) -> list[list[Tile]]:
    """A FLOOR interior enclosed by a WALL border (open arena for walking)."""
    return [
        [
            Tile.WALL if x in (0, width - 1) or y in (0, height - 1) else Tile.FLOOR
            for x in range(width)
        ]
        for y in range(height)
    ]


def _walk(seed: int, steps: int, start: tuple[int, int]):
    world = FiniteWorld(_open_field())
    rng = random.Random(seed)
    agent = AgentState(x=start[0], y=start[1])
    positions = []
    for _ in range(steps):
        tick(agent, world, rng, DEFAULT_CONFIG)
        positions.append((agent.x, agent.y))
    return agent, positions


def test_tick_moves_at_most_one_cell_per_tick():
    _, positions = _walk(0, 1000, (48, 27))
    previous = (48, 27)
    for current in positions:
        assert max(abs(current[0] - previous[0]), abs(current[1] - previous[1])) <= 1
        previous = current


def test_tick_never_enters_a_wall():
    tiles = _open_field()
    world = FiniteWorld(tiles)
    rng = random.Random(99)
    agent = AgentState(x=48, y=27)
    for _ in range(2000):
        tick(agent, world, rng, DEFAULT_CONFIG)
        assert tiles[agent.y][agent.x] is Tile.FLOOR


def test_tick_is_deterministic_under_a_fixed_seed():
    _, first = _walk(123, 500, (48, 27))
    _, second = _walk(123, 500, (48, 27))
    assert first == second


def test_tick_explores_instead_of_dithering():
    agent, positions = _walk(4, OPEN_FIELD_TICKS, (48, 27))
    assert len(agent.memory) > 3000  # the arena has 5044 tiles
    assert len(set(positions)) > 500


def test_tick_memory_contains_everywhere_the_agent_stood():
    agent, positions = _walk(5, 300, (48, 27))
    for position in positions:
        assert position in agent.memory


def test_tick_only_uses_passable_neighbors_in_a_corridor():
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR
    world = FiniteWorld(tiles)
    rng = random.Random(7)
    agent = AgentState(x=2, y=2)
    for _ in range(200):
        tick(agent, world, rng, DEFAULT_CONFIG)
        assert agent.y == 2
        assert 1 <= agent.x <= 3


def test_tick_stays_put_when_enclosed_by_walls():
    tiles = [[Tile.WALL] * 3 for _ in range(3)]
    tiles[1][1] = Tile.FLOOR
    world = FiniteWorld(tiles)
    agent = AgentState(x=1, y=1)
    for _ in range(100):
        tick(agent, world, random.Random(3), DEFAULT_CONFIG)
        assert (agent.x, agent.y) == (1, 1)


def test_tick_refuses_steps_that_world_truth_rejects():
    """A lied-to memory plans wall steps forever; physics refuses every one.

    Terrain beliefs are never revised (no decay until Phase 3), so the agent
    re-plans through the phantom corridor each tick — and still never enters
    the wall.
    """
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR  # truth: corridor ends at x = 3
    world = FiniteWorld(tiles)
    agent = AgentState(x=3, y=2)
    agent.memory.observe(
        {(x, 2): Tile.FLOOR for x in range(1, 6)}, tick=0
    )  # belief: corridor continues to x = 5
    for _ in range(10):
        tick(agent, world, random.Random(0), DEFAULT_CONFIG)
        assert tiles[agent.y][agent.x] is Tile.FLOOR  # physics never lied to
        assert agent.y == 2 and 1 <= agent.x <= 3  # real corridor only


def test_tick_refuses_to_step_into_liquid():
    """WATER/LAVA are impassable: a believed-passable pond is not entered."""
    tiles = [[Tile.WALL] * 5 for _ in range(5)]
    for x in range(1, 4):
        tiles[2][x] = Tile.FLOOR
    tiles[2][3] = Tile.WATER  # truth: the corridor drowns at x = 3
    world = FiniteWorld(tiles)
    agent = AgentState(x=2, y=2)
    agent.memory.observe(
        {(x, 2): Tile.FLOOR for x in range(1, 5)}, tick=0
    )  # belief: dry corridor to x = 4
    for _ in range(20):
        tick(agent, world, random.Random(0), DEFAULT_CONFIG)
        assert (agent.x, agent.y) == (2, 2) or tiles[agent.y][agent.x] is Tile.FLOOR
        assert not (agent.x == 3 and agent.y == 2)  # never stands in the water


class PopulatedWorld(FiniteWorld):
    """Finite world that also answers the entity questions a chunk store does."""

    def __init__(self, tiles, monsters=None) -> None:
        super().__init__(tiles)
        self.monsters = list(monsters or [])
        self.dropped = []

    def entity_at(self, x, y):
        for monster in self.monsters:
            if (monster.x, monster.y) == (x, y):
                return monster
        return None

    def item_at(self, x, y):
        return None

    def remove_entity(self, monster):
        self.monsters.remove(monster)

    def drop_item(self, kind, x, y):
        self.dropped.append((kind.key, x, y))

    @property
    def spawn(self):
        return (5, 5)

    def move_entity(self, monster, x, y):
        monster.x, monster.y = x, y

    def active_entities(self, origin, radius):
        return [
            monster
            for monster in self.monsters
            if max(abs(monster.x - origin[0]), abs(monster.y - origin[1])) <= radius
        ]


def _monster(x, y, glyph="g"):
    from sim.monsters import MONSTERS
    from world.populate import Monster

    kind = next(k for k in MONSTERS if k.glyph == glyph)
    return Monster(kind=kind, x=x, y=y, hp=kind.hp)


def test_only_entities_inside_the_activation_radius_are_active():
    """Everything further out stays inert data — the Phase 4 AI seam."""
    radius = DEFAULT_CONFIG.activation_radius
    near = _monster(20 + radius - 1, 20)
    edge = _monster(20 + radius, 20)
    far = _monster(20 + radius + 1, 20)
    world = PopulatedWorld(_open_field(), [near, edge, far])
    agent = AgentState(x=20, y=20)
    tick(agent, world, random.Random(1), DEFAULT_CONFIG)
    active = set(id(m) for m in agent.active_entities)
    assert id(near) in active
    assert id(edge) in active  # the radius is inclusive
    assert id(far) not in active


def test_a_world_without_entities_still_ticks():
    """The tick only asks for entities when the world offers them."""
    agent = AgentState(x=20, y=20)
    tick(agent, FiniteWorld(_open_field()), random.Random(1), DEFAULT_CONFIG)
    assert agent.active_entities == []


def test_the_agent_remembers_a_monster_it_walked_past():
    world = PopulatedWorld(_open_field(), [_monster(21, 20, "o")])
    agent = AgentState(x=20, y=20)
    tick(agent, world, random.Random(1), DEFAULT_CONFIG)
    assert agent.memory.snapshot((21, 20))[0] == "o"


def test_the_pruner_fires_on_its_interval_and_bounds_memory():
    from dataclasses import replace

    config = replace(DEFAULT_CONFIG, memory_ttl=40, memory_prune_interval=20)
    world = FiniteWorld(_open_field())
    agent = AgentState(x=20, y=20)
    rng = random.Random(3)
    for _ in range(19):
        tick(agent, world, rng, config)
    assert agent.pruned_total == 0  # interval has not come round yet
    seen_early = len(agent.memory)
    for _ in range(181):
        tick(agent, world, rng, config)
    assert agent.pruned_total > 0
    assert len(agent.memory) <= seen_early * 4  # bounded, not ever-growing


def test_monsters_outside_the_activation_radius_never_move():
    """The dormancy invariant. If distant monsters moved, a chunk's contents
    would depend on where the agent had wandered, not on its seed."""
    from world.chunks import ChunkStore

    world = ChunkStore(DEFAULT_CONFIG, world_seed=13)
    spawn = world.spawn
    agent = AgentState(x=spawn[0], y=spawn[1])
    rng = random.Random(2)
    for _ in range(30):  # let the world stream out around the agent
        tick(agent, world, rng, DEFAULT_CONFIG)

    radius = DEFAULT_CONFIG.activation_radius
    distant = [
        (monster, (monster.x, monster.y))
        for chunk in [world.get_chunk(cx, cy) for cx in (-1, 0, 1) for cy in (-1, 0, 1)]
        for monster in chunk.contents.monsters
        if max(abs(monster.x - agent.x), abs(monster.y - agent.y)) > radius * 2
    ]
    assert distant, "no distant monsters to check"
    for _ in range(60):
        tick(agent, world, rng, DEFAULT_CONFIG)
    for monster, was in distant:
        if max(abs(monster.x - agent.x), abs(monster.y - agent.y)) > radius:
            assert (monster.x, monster.y) == was


def test_a_run_with_moving_monsters_is_still_deterministic():
    from world.chunks import ChunkStore

    def run():
        world = ChunkStore(DEFAULT_CONFIG, world_seed=13)
        spawn = world.spawn
        agent = AgentState(x=spawn[0], y=spawn[1])
        rng = random.Random(2)
        for _ in range(120):
            tick(agent, world, rng, DEFAULT_CONFIG)
        positions = sorted(
            (m.x, m.y)
            for cx in (-1, 0, 1)
            for cy in (-1, 0, 1)
            for m in world.get_chunk(cx, cy).contents.monsters
        )
        return (agent.x, agent.y), positions

    assert run() == run()


def test_monsters_actually_move_when_the_agent_is_near():
    from world.chunks import ChunkStore

    world = ChunkStore(DEFAULT_CONFIG, world_seed=13)
    spawn = world.spawn
    agent = AgentState(x=spawn[0], y=spawn[1])
    rng = random.Random(2)
    before = {
        id(m): (m.x, m.y)
        for cx in (-1, 0, 1)
        for cy in (-1, 0, 1)
        for m in world.get_chunk(cx, cy).contents.monsters
    }
    for _ in range(80):
        tick(agent, world, rng, DEFAULT_CONFIG)
    after = {
        id(m): (m.x, m.y)
        for cx in (-1, 0, 1)
        for cy in (-1, 0, 1)
        for m in world.get_chunk(cx, cy).contents.monsters
    }
    assert any(before[k] != after[k] for k in before if k in after)


def test_the_agent_hits_what_it_walks_into_instead_of_walking_through_it():
    """Bump combat: the step is spent on the blow, the agent stays put."""
    from dataclasses import replace

    config = replace(DEFAULT_CONFIG, damage_variance=0)
    monster = _monster(21, 20, "T")  # tough enough to survive one hit
    world = PopulatedWorld(_open_field(), [monster])
    agent = AgentState(x=20, y=20)
    agent.explorer.path = [(21, 20)]
    before = monster.hp
    tick(agent, world, random.Random(1), config)
    assert (agent.x, agent.y) == (20, 20)
    assert monster.hp < before


def test_killing_a_monster_removes_it_and_pays_experience():
    from dataclasses import replace

    config = replace(DEFAULT_CONFIG, damage_variance=0, monster_drop_chance=1.0)
    monster = _monster(21, 20, "r")  # 3 hp against a 5-attack agent: one blow
    world = PopulatedWorld(_open_field(), [monster])
    agent = AgentState(x=20, y=20)
    agent.explorer.path = [(21, 20)]
    tick(agent, world, random.Random(1), config)
    assert monster not in world.monsters
    assert agent.kills == 1
    assert agent.stats.xp > 0 or agent.stats.level > 1
    assert world.dropped  # drop chance 1.0: the corpse left something


def test_a_corpse_leaves_nothing_when_the_drop_roll_fails():
    from dataclasses import replace

    config = replace(DEFAULT_CONFIG, damage_variance=0, monster_drop_chance=0.0)
    world = PopulatedWorld(_open_field(), [_monster(21, 20, "r")])
    agent = AgentState(x=20, y=20)
    agent.explorer.path = [(21, 20)]
    tick(agent, world, random.Random(1), config)
    assert agent.kills == 1
    assert world.dropped == []


def test_death_resets_the_body_marks_the_spot_and_keeps_the_mind():
    """The aquarium's bargain: start over weak, but not ignorant."""
    world = PopulatedWorld(_open_field(), [_monster(21, 20, "D")])
    agent = AgentState(x=20, y=20)
    rng = random.Random(1)
    tick(agent, world, rng, DEFAULT_CONFIG)
    agent.stats.hp = 1  # on the brink, with a dragon adjacent
    remembered = len(agent.memory)
    assert remembered > 0
    for _ in range(30):
        tick(agent, world, rng, DEFAULT_CONFIG)
        if agent.deaths:
            break
    assert agent.deaths == 1
    assert (agent.x, agent.y) == world.spawn
    assert agent.stats.hp == agent.stats.max_hp == DEFAULT_CONFIG.agent_max_hp
    assert agent.stats.level == 1
    assert len(agent.memory) >= remembered  # memory survives death
    assert any(kind == "grave" for kind, _, _ in world.dropped)


def test_the_agent_gets_its_stats_without_being_handed_them():
    agent = AgentState(x=20, y=20)
    assert agent.stats is None
    tick(agent, FiniteWorld(_open_field()), random.Random(1), DEFAULT_CONFIG)
    assert agent.stats.hp == DEFAULT_CONFIG.agent_max_hp


def test_after_death_the_agent_has_looked_at_where_it_woke_up():
    """A brain deciding from an unobserved tile does not believe its own feet
    are on solid ground, and strands itself with nothing reachable."""
    world = PopulatedWorld(_open_field(), [_monster(21, 20, "D")])
    agent = AgentState(x=20, y=20)
    rng = random.Random(1)
    tick(agent, world, rng, DEFAULT_CONFIG)
    agent.stats.hp = 1
    for _ in range(30):
        tick(agent, world, rng, DEFAULT_CONFIG)
        if agent.deaths:
            break
    assert agent.deaths == 1
    assert agent.memory.believes_passable((agent.x, agent.y))


def test_fear_takes_the_wheel_off_exploration():
    """A dragon in view should move the agent away, whatever EXPLORE wanted."""
    world = PopulatedWorld(_open_field(), [_monster(24, 20, "D")])
    agent = AgentState(x=20, y=20)
    rng = random.Random(5)
    tick(agent, world, rng, DEFAULT_CONFIG)  # look, and see the dragon
    assert agent.memory.snapshot((24, 20))[0] == "D"
    assert agent.fleer.active, "a dragon four tiles away should trigger flight"
    before = agent.x
    for _ in range(6):
        tick(agent, world, rng, DEFAULT_CONFIG)
    assert agent.x < before  # ground given, away from the dragon


def test_the_agent_goes_back_to_exploring_once_it_is_calm():
    world = PopulatedWorld(_open_field(), [_monster(24, 20, "D")])
    agent = AgentState(x=20, y=20)
    rng = random.Random(5)
    tick(agent, world, rng, DEFAULT_CONFIG)
    assert agent.fleer.active
    world.monsters.clear()
    for _ in range(DEFAULT_CONFIG.memory_ttl + 5):
        tick(agent, world, rng, DEFAULT_CONFIG)
        if not agent.fleer.active:
            break
    assert not agent.fleer.active
