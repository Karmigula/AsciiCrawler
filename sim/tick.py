"""Pygame-free simulation tick: feet, eyes, brain — in that order.

The world argument is anything offering `ensure_loaded(position)` and
`tile_at(x, y) -> Tile` (ChunkStore in production, tiny stubs in tests).
Each tick: stream chunks around the agent (a cheap radius check), act (one
step along the current plan, or wander by belief), observe (FOV over a
window of global coordinates fetched through `tile_at` — the only channel
from world truth to belief), think (re-decide when the throttle fires).
The brain never reads world tiles; only `_try_step` does, as physics: it is
where a stale belief will someday produce a refused step instead of a walk
through a wall.

Two Phase 3 additions ride along. The pruner sweeps expired memory on its own
interval, which is what keeps the belief dict bounded over a long run. And the
active-entity scan collects the monsters inside `activation_radius` each tick,
and those monsters then take their turn (`sim.ai`). Only the active set moves:
that is what keeps a chunk's contents a function of its seed rather than of
wherever the agent has previously wandered.

Agent position is unbounded global coordinates; nothing here knows about
chunk boundaries.
"""

import random
from dataclasses import dataclass, field

from agent.fov import compute_fov
from agent.goals import DIRS_8, ExploreGoal, FleeGoal, LootGoal
from agent.loadout import best_assignment, derive, effective_config, score
from agent.memory import Memory
from config import Config
from agent.stats import Stats
from sim.ai import take_turns
from sim.combat import agent_hits_monster, xp_for
from sim.perks import on_kill
from sim.items import GRAVE


@dataclass
class AgentState:
    """What the tick needs to know about the agent: where it stands,
    what it remembers, and what it is currently chasing."""

    x: int
    y: int
    memory: Memory = field(default_factory=Memory)
    explorer: ExploreGoal = field(default_factory=ExploreGoal)
    fleer: FleeGoal = field(default_factory=FleeGoal)
    looter: LootGoal = field(default_factory=LootGoal)
    equipped: dict = field(default_factory=dict)
    backpack: list = field(default_factory=list)
    gold: int = 0
    potions: int = 0
    pickups: int = 0
    goal_name: str = "EXPLORE"
    derived: object = None
    _loadout_signature: tuple = ()
    tick_count: int = 0
    active_entities: list = field(default_factory=list)
    pruned_total: int = 0
    stats: Stats | None = None  # filled from config on the first tick
    kills: int = 0
    deaths: int = 0
    traps_found: int = 0
    traps_sprung: int = 0
    damage_taken: int = 0


def tick(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Advance the world by one tick, in place. Deterministic for a fixed
    world seed, identically-seeded rng, and config."""
    agent.tick_count += 1
    if agent.stats is None:
        agent.stats = Stats.starting(config)
    mind = _refresh_loadout(agent, config)
    world.ensure_loaded((agent.x, agent.y))
    _act(agent, world, rng, config)
    _observe(agent, world, mind)
    _pick_up(agent, world, config)
    _quaff(agent, config)
    _spot_traps(agent, world, rng, config)
    _forget(agent, mind)
    _scan_active(agent, world, config)
    _monsters_act(agent, world, rng, config)
    _resolve_death(agent, world, config)
    _respawn_pass(agent, world, config)
    _think(agent, rng, _refresh_loadout(agent, config))


def _refresh_loadout(agent: AgentState, config: Config) -> Config:
    """Recompute derived stats when the loadout or the body has changed.

    Guarded by a signature rather than a dirty flag: levelling changes the body
    from inside Stats, where a flag would have to be remembered to set, and a
    stale derived bundle is the kind of bug that shows up as the agent quietly
    ignoring the ring it just put on. The signature makes staleness impossible
    instead of unlikely.
    """
    stats = agent.stats
    signature = (
        stats.attack,
        stats.defense,
        stats.max_hp,
        tuple(sorted((slot, id(item)) for slot, item in agent.equipped.items())),
    )
    if signature != agent._loadout_signature or agent.derived is None:
        agent._loadout_signature = signature
        agent.derived = derive(stats, agent.equipped, config)
        agent._mind = effective_config(config, agent.derived)
    return agent._mind


def _pick_up(agent: AgentState, world, config: Config) -> None:
    """Take whatever is underfoot and re-think what to wear."""
    take = getattr(world, "take_item", None)
    if take is None:
        return
    item = take(agent.x, agent.y)
    if item is None:
        return
    agent.pickups += 1
    if item.kind.key == "gold":
        agent.gold += 1
        return
    if item.kind.key == "potion":
        agent.potions += 1
        return
    if item.kind.key == "grave":
        return  # a headstone is scenery, not loot
    _reconsider_loadout(agent, item, config)


def _reconsider_loadout(agent: AgentState, item, config: Config) -> None:
    """Wear the best set available; keep near-misses, drop the dead weight.

    The swap has to clear `equip_margin` so the agent does not spend its life
    changing rings for a rounding error.
    """
    owned = [*agent.backpack, item, *agent.equipped.values()]
    current = score(derive(agent.stats, agent.equipped, config), config)
    proposal = best_assignment(agent.stats, owned, config)
    if score(derive(agent.stats, proposal, config), config) > current + config.equip_margin:
        agent.equipped = proposal
    worn = {id(i) for i in agent.equipped.values()}
    spares = [i for i in owned if id(i) not in worn]
    spares.sort(
        key=lambda i: -score(derive(agent.stats, {i.kind.slot: i}, config), config)
    )
    agent.backpack = spares[: config.backpack_size]


def _quaff(agent: AgentState, config: Config) -> None:
    """Drink when actually hurt. Potions are the agent's only self-repair."""
    if not agent.potions or agent.derived is None:
        return
    if agent.stats.hp > agent.derived.max_hp * config.potion_at_hp_fraction:
        return
    agent.potions -= 1
    agent.stats.hp = min(agent.derived.max_hp, agent.stats.hp + config.potion_heal)


def _act(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    if agent.fleer.active:
        driver = agent.fleer
    elif agent.looter.path:
        driver = agent.looter
    else:
        driver = agent.explorer
    if driver.path:
        if _try_step(agent, driver.path[0], world, rng, config):
            driver.path.pop(0)
        else:
            driver.drop_plan()  # blocked: physics disagrees with belief
        return
    # idle fallback: wander to a believed-passable neighbour, corner-cut safe
    options = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in DIRS_8
        if _wander_ok(agent, dx, dy)
    ]
    if options:
        _try_step(agent, rng.choice(options), world, rng, config)


def _wander_ok(agent: AgentState, dx: int, dy: int) -> bool:
    if dx != 0 and dy != 0 and not (
        agent.memory.believes_passable((agent.x + dx, agent.y))
        and agent.memory.believes_passable((agent.x, agent.y + dy))
    ):
        return False
    target = (agent.x + dx, agent.y + dy)
    return agent.memory.believes_passable(target) and not agent.memory.believes_hazard(
        target
    )


def _try_step(
    agent: AgentState, nxt: tuple[int, int], world, rng: random.Random, config: Config
) -> bool:
    """Move one cell — or, if something is standing there, hit it instead.

    Bump combat: the agent has no attack command, so a step into an occupied
    tile spends itself as a blow. The step counts as taken either way, which
    is what stops a plan from spinning on a blocked tile.
    """
    dx, dy = nxt[0] - agent.x, nxt[1] - agent.y
    if max(abs(dx), abs(dy)) != 1:
        return False
    if not world.tile_at(nxt[0], nxt[1]).passable:
        return False
    entity_at = getattr(world, "entity_at", None)
    monster = None if entity_at is None else entity_at(nxt[0], nxt[1])
    if monster is not None:
        agent_hits_monster(agent.stats, monster, rng, config)
        if monster.hp <= 0:
            _kill(agent, monster, world, rng, config)
        return True
    agent.x, agent.y = nxt
    _spring_trap(agent, world, config)
    return True


def _spring_trap(agent: AgentState, world, config: Config) -> None:
    """Stepping on a hidden trap sets it off; a known one is just scenery."""
    trap_at = getattr(world, "trap_at", None)
    if trap_at is None:
        return
    trap = trap_at(agent.x, agent.y)
    if trap is None or not trap.hidden:
        return
    trap.hidden = False
    agent.damage_taken += agent.stats.take(config.trap_damage)
    agent.traps_sprung += 1
    agent.memory.mark_hazard(
        (agent.x, agent.y), agent.tick_count, world.tile_at(agent.x, agent.y)
    )


def _spot_traps(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Roll to notice nearby traps, and remember the ones already revealed."""
    traps_near = getattr(world, "traps_near", None)
    if traps_near is None:
        return
    for trap in traps_near((agent.x, agent.y), config.trap_detect_radius):
        coord = (trap.x, trap.y)
        if trap.hidden:
            if rng.random() >= config.trap_detect_chance:
                continue
            trap.hidden = False
            agent.traps_found += 1
        if not agent.memory.believes_hazard(coord):
            agent.memory.mark_hazard(coord, agent.tick_count, world.tile_at(*coord))


def _kill(agent: AgentState, monster, world, rng: random.Random, config: Config) -> None:
    """Remove a dead monster, maybe leave its belongings, bank the experience."""
    where = (monster.x, monster.y)
    world.remove_entity(monster)
    agent.kills += 1
    agent.stats.gain_xp(xp_for(monster, config), config)
    if agent.derived is not None:
        on_kill(agent.derived, agent.stats, config)
    if rng.random() < config.monster_drop_chance:
        from sim.items import ITEMS

        world.drop_item(ITEMS[rng.randrange(len(ITEMS))], *where, rng=rng)


def _resolve_death(agent: AgentState, world, config: Config) -> None:
    """If the agent died: mark the spot, start over weak, keep every memory.

    Memory surviving death is the aquarium's central bargain — the creature
    starts again at level 1 but not at square one, so it does not re-run its
    first ten minutes forever.
    """
    if agent.stats.alive:
        return
    if hasattr(world, "drop_item"):
        world.drop_item(GRAVE, agent.x, agent.y)
    agent.deaths += 1
    agent.stats = Stats.starting(config)
    agent.fleer.stand_down()
    spawn = getattr(world, "spawn", (agent.x, agent.y))
    agent.x, agent.y = spawn
    agent.explorer.drop_plan()
    agent.looter.clear()
    # Look before thinking. The body has just been moved across the world, so
    # the observation taken earlier this tick describes somewhere else — and a
    # brain that decides from an unobserved tile does not believe its own feet
    # are on solid ground, which strands it with an empty reachable set.
    _observe(agent, world, config)


def _respawn_pass(agent: AgentState, world, config: Config) -> None:
    """Let cleared chunks refill, on an interval and never near the agent."""
    if agent.tick_count % config.respawn_check_interval:
        return
    sweep = getattr(world, "respawn_pass", None)
    if sweep is not None:
        sweep((agent.x, agent.y), agent.tick_count, config)


def _observe(agent: AgentState, world, config: Config) -> None:
    """FOV through a (2r+1)-square window of global tiles around the agent.

    Tiles beyond the window are at distance >= radius and invisible anyway,
    so window semantics equal infinite-world semantics. The window is built
    through `tile_at`, never by reaching into chunk internals.
    """
    radius = config.fov_radius
    origin_x, origin_y = agent.x - radius, agent.y - radius
    window = [
        [world.tile_at(origin_x + lx, origin_y + ly) for lx in range(2 * radius + 1)]
        for ly in range(2 * radius + 1)
    ]
    visible = compute_fov(window, (radius, radius), radius)
    observation = {
        (origin_x + lx, origin_y + ly): window[ly][lx] for lx, ly in visible
    }
    entities, items = _things_seen(world, observation)
    agent.memory.observe(observation, agent.tick_count, entities, items)


def _things_seen(world, observation) -> tuple[dict, dict]:
    """Glyphs of whatever stands on the visible tiles, for memory snapshots.

    Worlds that carry no entities (the tiny stubs the tick tests use) simply
    do not offer these lookups, and the agent then remembers terrain alone.
    """
    entity_at = getattr(world, "entity_at", None)
    item_at = getattr(world, "item_at", None)
    entities: dict = {}
    items: dict = {}
    if entity_at is None and item_at is None:
        return entities, items
    for coord in observation:
        if entity_at is not None:
            monster = entity_at(*coord)
            if monster is not None:
                entities[coord] = monster.kind.glyph
        if item_at is not None:
            item = item_at(*coord)
            if item is not None:
                items[coord] = item.kind.glyph
    return entities, items


def _forget(agent: AgentState, config: Config) -> None:
    """Sweep expired memory on the pruner interval (cheap, not every tick)."""
    if agent.tick_count % config.memory_prune_interval:
        return
    agent.pruned_total += agent.memory.prune(agent.tick_count, config.memory_ttl)


def _scan_active(agent: AgentState, world, config: Config) -> None:
    """Collect the entities near enough to matter. Frozen until Phase 4."""
    scan = getattr(world, "active_entities", None)
    if scan is None:
        return
    agent.active_entities = scan((agent.x, agent.y), config.activation_radius)


def _monsters_act(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Give the active monsters their turn. Worlds without them just skip it."""
    if not agent.active_entities or not hasattr(world, "move_entity"):
        return
    agent.damage_taken += take_turns(
        agent, agent.active_entities, world, rng, config, agent.tick_count
    )


def _think(agent: AgentState, rng: random.Random, config: Config) -> None:
    """Fear first, curiosity second.

    FLEE pre-empts rather than competing on score: a utility comparison would
    let a good enough exploration prospect talk the agent into standing next
    to a troll, and "why is it doing that" should be answerable by looking.
    """
    here = (agent.x, agent.y)
    if agent.fleer.wants_control(here, agent.memory, agent.stats, config):
        agent.explorer.drop_plan()
        agent.looter.clear()
        agent.fleer.decide(here, agent.memory, config)
        agent.goal_name = "FLEE"
        return
    if agent.fleer.active:
        agent.fleer.stand_down()
    if agent.looter.path:
        agent.goal_name = "LOOT"
        return  # already on the way to something
    if not agent.explorer.wants_rethink(
        agent.memory, agent.tick_count, config.explore_throttle_ticks
    ):
        return
    if agent.looter.decide(here, agent.memory, agent.equipped, config) is not None:
        agent.explorer.drop_plan()
        agent.goal_name = "LOOT"
        return
    agent.goal_name = "EXPLORE"
    agent.explorer.decide(here, agent.memory, rng, config, agent.tick_count)
