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

MOVED = "moved"
ATTACKED = "attacked"
BLOCKED = "blocked"

from agent.fov import compute_fov
from agent.goals import DIRS_8, ExploreGoal, FleeGoal, LootGoal
from agent.loadout import archetype, best_assignment, derive, effective_config, score
from agent.memory import Memory
from config import Config
from world.tiles import Tile
from agent.stats import Stats
from sim.ai import take_turns
from sim.combat import agent_hits_monster, xp_for
from sim import chronicle as story
from sim import effects as status
from sim import names
from sim import bosses as boss_table
from sim import monsters as monsters_module
from sim import spells as magic
from sim.chronicle import Chronicle
from sim.hall import Fallen
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
    name: str = ""
    # Every tile entered this tick. Usually one; on ice, the whole skid.
    crossed: list = field(default_factory=list)
    # Blessings and curses currently running: {key: ticks left}.
    effects: dict = field(default_factory=dict)
    # Spell cooldowns, {key: ticks left}; absent means ready.
    cooldowns: dict = field(default_factory=dict)
    casts: int = 0
    # The wandering named thing currently after it, if any.
    roaming_boss: object = None
    derived: object = None
    _mind: object = None
    _loadout_signature: tuple = ()

    def mind(self, config: Config) -> Config:
        """The config the brain is actually running on.

        Cognition affixes are folded in here, so the renderer showing a sight
        radius or a memory age is showing the one the agent is really using
        rather than the one written in the config file. Falls back to the base
        config before the first tick has built the loadout.
        """
        return self._mind if self._mind is not None else config
    tick_count: int = 0
    active_entities: list = field(default_factory=list)
    pruned_total: int = 0
    stats: Stats | None = None  # filled from config on the first tick
    kills: int = 0
    deaths: int = 0
    traps_found: int = 0
    traps_sprung: int = 0
    shrines_touched: int = 0
    # Per-life, reset on death: a hall of fame entry is one life, not a career.
    life_kills: int = 0
    life_depth: int = 0
    life_started: int = 0
    last_wound: str = "the dark"
    fallen: list = field(default_factory=list)
    graves_robbed: int = 0
    grave_sites: set = field(default_factory=set)
    heat_damage: int = 0
    log: Chronicle = field(default_factory=Chronicle)
    damage_taken: int = 0


def tick(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Advance the world by one tick, in place. Deterministic for a fixed
    world seed, identically-seeded rng, and config."""
    agent.tick_count += 1
    if agent.stats is None:
        agent.stats = Stats.starting(config)
        agent.log = Chronicle(limit=config.chronicle_length)
        if not agent.name:
            # Named from the world's seed and how many lives have ended here,
            # rather than from `rng`: drawing from the tick's stream would
            # shift every roll after it, and a name should not move a monster.
            agent.name = names.name_for(getattr(world, "seed", 0), agent.deaths)
    _touch_shrine(agent, world, rng, config)
    mind = _refresh_loadout(agent, config)
    world.ensure_loaded((agent.x, agent.y))
    if not _cast(agent, world, rng, config) and not _kite(agent, world, config):
        _act(agent, world, rng, config)
    _observe(agent, world, mind)
    _pick_up(agent, world, config)
    _quaff(agent, config)
    _burn(agent, world, config)
    _choke(agent, world, config)
    _spot_traps(agent, world, rng, config)
    _wake_thrones(agent, world, config)
    _send_a_boss(agent, world, rng, config)
    _fade_effects(agent)
    magic.tick(agent.cooldowns)
    agent.life_depth = max(
        agent.life_depth, int((agent.x * agent.x + agent.y * agent.y) ** 0.5)
    )
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
        tuple(
            sorted(
                # By value, not by id(): CPython reuses addresses, so a
                # replacement item allocated where a discarded one used to live
                # would produce an identical signature and leave the derived
                # bundle describing gear the agent is no longer wearing.
                (slot, item.kind.key, item.rarity, tuple(a.key for a in item.affixes))
                for slot, item in agent.equipped.items()
            )
        ),
        # Which effects are running, not how long they have left: the
        # modifiers depend on the set, and putting the countdown in here would
        # rebuild the whole bundle every tick for no change at all.
        tuple(sorted(agent.effects)),
    )
    if signature != agent._loadout_signature or agent.derived is None:
        agent._loadout_signature = signature
        agent.derived = derive(stats, agent.equipped, config, agent.effects)
        agent._mind = effective_config(config, agent.derived)
    return agent._mind


def _boss_monster(kind_key: str, level: int, x: int, y: int, seed: int, config):
    """Build a named thing at the level it is being met at."""
    from world.populate import Monster

    boss = next(b for b in boss_table.BOSSES if b.key == kind_key)
    kind = boss_table.scaled(boss, level, config)
    rng = random.Random((seed * 31 + x) * 31 + y)
    return Monster(
        kind=kind,
        x=x,
        y=y,
        hp=kind.hp,
        name=f"{names.given_name(rng)}, {boss.title}",
    )


def _wake_thrones(agent: AgentState, world, config: Config) -> None:
    """Put the throned boss on its feet when the agent gets close enough.

    Built here rather than at worldgen so its numbers come from the level the
    creature actually arrived at. A boss rolled when the chunk was made is a
    wall if the agent finds it early and furniture if it finds it late, and
    neither is a fight.
    """
    if agent.stats is None or agent.stats.level < config.boss_level:
        return
    look = getattr(world, "thrones_near", None)
    if look is None:
        return
    for chunk in look((agent.x, agent.y), config.chunk_size):
        x, y, key = chunk.contents.throne
        chunk.contents.throne = None
        monster = _boss_monster(
            key, agent.stats.level, x, y, getattr(world, "seed", 0), config
        )
        chunk.contents.monsters.append(monster)
        chunk.contents.invalidate()
        agent.log.record(agent.tick_count, story.boss_stirs(monster.name))


def _send_a_boss(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Now and then, set something named wandering toward the agent.

    Only once the creature is worth hunting, only one at a time, and never
    within sight - a boss that appears next to you is a bug rather than a
    fight. It walks in like anything else, which means it can also be met by
    accident on the way somewhere.
    """
    if agent.stats is None or agent.stats.level < config.boss_level:
        return
    if agent.tick_count % max(1, config.boss_roam_interval):
        return
    if agent.roaming_boss is not None and agent.roaming_boss.hp > 0:
        return
    if rng.random() >= config.boss_roam_chance:
        return
    spawn = getattr(world, "spawn_monster", None)
    if spawn is None:
        return

    for _ in range(24):
        distance = rng.randint(config.boss_roam_min_distance, config.boss_roam_max_distance)
        angle = rng.uniform(0, 6.283185)
        import math

        x = agent.x + int(distance * math.cos(angle))
        y = agent.y + int(distance * math.sin(angle))
        # Checked in the same measure sight uses. Picking a point on a circle
        # gives a Euclidean distance, and on a diagonal that is a third
        # shorter in Chebyshev terms - which is how a boss meant to arrive
        # fourteen tiles out turned up thirteen away, inside the range this
        # was supposed to keep it out of.
        if _chebyshev((x, y), (agent.x, agent.y)) < config.boss_roam_min_distance:
            continue
        if not world.tile_at(x, y).passable:
            continue
        if world.entity_at(x, y) is not None:
            continue
        biome = world.biome_at(x, y)
        boss = boss_table.roamer_for(biome.key)
        monster = _boss_monster(
            boss.key, agent.stats.level, x, y, getattr(world, "seed", 0), config
        )
        spawn(monster)
        agent.roaming_boss = monster
        agent.log.record(agent.tick_count, story.boss_hunts(monster.name))
        return


def _kite(agent: AgentState, world, config: Config) -> bool:
    """Back away from something big while the spell reloads. True if it moved.

    Only for a creature that has a spell at all - backing away is pointless
    otherwise, since it has nothing to do with the distance it just bought.
    And only from something worth the trouble: retreating from a rat would
    read as cowardice rather than tactics, and would never end, because the
    rat follows.

    Cornered, it stops kiting and fights, which is the right answer and also
    the only one: there is nowhere to go.
    """
    derived = agent.derived
    if derived is None or not derived.spells:
        return False
    if not agent.cooldowns:
        return False  # something is ready; shoot rather than shuffle
    entity_at = getattr(world, "entity_at", None)
    if entity_at is None:
        return False

    here = (agent.x, agent.y)
    crowding = [
        monster
        for dx, dy in DIRS_8
        if (monster := entity_at(here[0] + dx, here[1] + dy)) is not None
        and monster.kind.threat >= config.kite_threat_floor
    ]
    if not crowding:
        return False

    away = _step_away(agent, world, entity_at, crowding)
    if away is None:
        return False  # cornered: turn and fight
    agent.x, agent.y = away
    agent.crossed = [away, *_slide(agent, away[0] - here[0], away[1] - here[1], world, config)]
    _spring_trap(agent, world, config)
    agent.explorer.drop_plan()
    agent.looter.clear()
    return True


def _step_away(agent: AgentState, world, entity_at, crowding) -> tuple | None:
    """The neighbouring tile that puts the most distance between them."""
    here = (agent.x, agent.y)
    current = min(_chebyshev(here, (m.x, m.y)) for m in crowding)
    best = None
    best_gap = current
    for dx, dy in DIRS_8:
        step = (here[0] + dx, here[1] + dy)
        if not world.tile_at(*step).passable:
            continue
        if dx and dy and not (
            world.tile_at(here[0] + dx, here[1]).passable
            and world.tile_at(here[0], here[1] + dy).passable
        ):
            continue  # the same corner rule the planner uses
        if entity_at(*step) is not None:
            continue
        gap = min(_chebyshev(step, (m.x, m.y)) for m in crowding)
        if gap > best_gap:
            best, best_gap = step, gap
    return best


def _chebyshev(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _cast(agent: AgentState, world, rng: random.Random, config: Config) -> bool:
    """Throw something at the nearest monster in reach. True if it spent the tick.

    Only at things the agent can see now, and only in a straight-ish line -
    the same Chebyshev reach everything else here measures in. A spell is the
    one thing the creature can do at a distance, so it is tried before
    walking: stepping into range and being hit on the way is the mistake this
    ordering exists to avoid.
    """
    derived = agent.derived
    if derived is None or not derived.spells:
        return False
    available = magic.ready(derived.spells, agent.cooldowns)
    if not available:
        return False
    entity_at = getattr(world, "entity_at", None)
    if entity_at is None:
        return False

    here = (agent.x, agent.y)
    best = None
    for spell in available:
        target = _nearest_within(agent, world, entity_at, spell.reach)
        if target is not None:
            best = (spell, target)
            break
    if best is None:
        return False

    spell, monster = best
    monster.hp -= spell.damage
    agent.cooldowns[spell.key] = spell.cooldown
    agent.casts += 1
    if spell.inflicts:
        monsters_module.afflict(monster, spell.inflicts)
    agent.log.record(agent.tick_count, story.cast(spell.label, monster.kind.key))
    if monster.hp <= 0:
        _kill(agent, monster, world, rng, config)
    return True


def _nearest_within(agent: AgentState, world, entity_at, reach: int):
    """The closest monster the agent can see within `reach`, or None.

    Walks outward so the first hit is the nearest; the agent should be
    shooting whatever is about to reach it rather than whatever it noticed
    first.
    """
    for radius in range(1, reach + 1):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                coord = (agent.x + dx, agent.y + dy)
                monster = entity_at(*coord)
                if monster is not None:
                    return monster
    return None


def _touch_shrine(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    """Standing on a totem is asking it a question. It answers once.

    Rolled here rather than when the chunk was built, so walking over to one
    is a decision made under real uncertainty: the agent cannot know whether
    the rimed effigy in the frozen deep is worth the trip, and neither can
    anybody watching.
    """
    look = getattr(world, "shrine_at", None)
    if look is None:
        return
    for coord in agent.crossed or [(agent.x, agent.y)]:
        shrine = look(*coord)
        if shrine is None or shrine.spent:
            continue
        shrine.spent = True
        blessed = rng.random() < shrine.blessing_chance
        pool = status.BLESSINGS if blessed else status.CURSES
        key = pool[rng.randrange(len(pool))]
        status.apply(agent.effects, key)
        agent.shrines_touched += 1
        agent.log.record(
            agent.tick_count, story.touched_shrine(shrine.kind, key, blessed)
        )


def _fade_effects(agent: AgentState) -> None:
    """Count everything running down, and say so when one lets go."""
    for key in status.tick(agent.effects):
        kind = status.BY_KEY.get(key)
        if kind is not None:
            agent.log.record(agent.tick_count, story.effect_ended(kind.label))


def _pick_up(agent: AgentState, world, config: Config) -> None:
    """Take whatever the agent went over this tick, and re-think what to wear.

    Everything it crossed, not only the tile it stopped on. A slide finishes
    further along than it began, so loot lying on a drift could not be stood
    on at all: the agent planned onto it, the ice took it past, and it planned
    onto it again. One run spent sixteen thousand ticks on a single amulet.

    Scooping it up in passing is also the better answer than refusing to go
    for it. Skidding across the ice and coming away with something is exactly
    what the terrain should feel like.
    """
    take = getattr(world, "take_item", None)
    peek = getattr(world, "item_at", None)
    if take is None or peek is None:
        return
    for coord in agent.crossed or [(agent.x, agent.y)]:
        _take_one(agent, world, config, coord, take, peek)
    agent.crossed = []


def _take_one(agent: AgentState, world, config: Config, coord, take, peek) -> None:
    """Lift whatever is on one tile the agent covered."""
    resting = peek(*coord)
    if resting is None:
        return
    if resting.kind.key == "grave":
        return  # a headstone is scenery: look, do not lift
    item = take(*coord)
    if item is None:
        return
    agent.pickups += 1
    here = coord
    # Only equippable gear counts as robbing a grave, and only while something
    # of the agent's is still lying there: otherwise a headstone tile reports a
    # robbery forever, including for unrelated loot that later falls on it.
    if here in agent.grave_sites and item.kind.slot is not None:
        agent.graves_robbed += 1
        agent.log.record(agent.tick_count, story.robbed_grave())
        left = peek(agent.x, agent.y)
        # The headstone stays put forever, so "nothing left" has to mean
        # "nothing but the grave" - otherwise the site is never forgotten and
        # every later drop on that tile reads as robbing it again.
        if left is None or left.kind.key == "grave":
            agent.grave_sites.discard(here)
    else:
        agent.log.record(agent.tick_count, story.found(item))
    if item.kind.key == "gold":
        agent.gold += 1
        return
    if item.kind.key == "potion":
        agent.potions += 1
        return
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


def current_driver(agent: AgentState):
    """Whichever goal currently holds the wheel: fear, then greed, then curiosity.

    Public because the PLAN overlay has to draw the same goal the agent is
    actually walking. Two copies of this precedence would drift, and the
    overlay exists to answer "why is it doing that" - a drifted copy answers
    it wrongly.
    """
    if agent.fleer.active:
        return agent.fleer
    if agent.looter.path:
        return agent.looter
    return agent.explorer


def _act(agent: AgentState, world, rng: random.Random, config: Config) -> None:
    driver = current_driver(agent)
    if driver.path:
        outcome = _try_step(agent, driver.path[0], world, rng, config)
        if outcome == MOVED:
            _advance_plan(driver, (agent.x, agent.y))
        elif outcome == BLOCKED:
            driver.drop_plan()  # blocked: physics disagrees with belief
        # ATTACKED: the blow spent the tick but the body did not move, so the
        # plan still starts from where the agent is standing. Popping here
        # would leave the next step two tiles away, which the sanity check
        # then rejects - dropping the plan and, mid-flight, handing the agent
        # to random wander with a monster adjacent.
        return
    # idle fallback: wander to a believed-passable neighbour, corner-cut safe
    options = [
        (agent.x + dx, agent.y + dy)
        for dx, dy in DIRS_8
        if _wander_ok(agent, dx, dy)
    ]
    if not options:
        # Every way out is a tile the agent knows is trapped. A dead-end
        # corridor whose only opening holds a trap would otherwise cage it for
        # the rest of the run - and standing still refreshes that trap's record
        # every tick, so the knowledge caging it never expires either. Six
        # points of damage is cheaper than never moving again.
        options = [
            (agent.x + dx, agent.y + dy)
            for dx, dy in DIRS_8
            if _wander_ok(agent, dx, dy, allow_hazard=True)
        ]
    if options:
        _try_step(agent, rng.choice(options), world, rng, config)


def _wander_ok(agent: AgentState, dx: int, dy: int, allow_hazard: bool = False) -> bool:
    if dx != 0 and dy != 0 and not (
        agent.memory.believes_passable((agent.x + dx, agent.y))
        and agent.memory.believes_passable((agent.x, agent.y + dy))
    ):
        return False
    target = (agent.x + dx, agent.y + dy)
    if not agent.memory.believes_passable(target):
        return False
    return allow_hazard or not agent.memory.believes_hazard(target)


def _advance_plan(driver, landed: tuple[int, int]) -> None:
    """Drop the plan up to wherever the agent actually ended up.

    A step is one tick but not always one tile: ice carries the agent on, and
    a slide-aware plan lists every tile it crosses. Popping a single entry per
    move would leave the plan trailing behind the body by the length of the
    slide, and the next step would be several tiles away - which physics
    refuses, so the plan gets thrown away and rebuilt every time the agent
    touches ice.

    Looking for the landing tile rather than counting tiles means a slide that
    ran short - into a monster, or into ground the agent had misremembered -
    still leaves the plan pointing at the right place.

    Throwing the plan away whenever the landing was a surprise was measurably
    worse than keeping it: over sixteen worlds the agent got 493 tiles from
    spawn rather than 526. A route the agent overshot mostly still goes
    somewhere worth going.
    """
    if not driver.path:
        return
    # The landing may be anywhere along the route, not just one step in: a
    # slide can carry the agent several tiles down its own plan, or past the
    # tile it aimed at. Wherever on the plan it ended up, the rest of that
    # plan still leads where it was going, so cut there and keep walking.
    for index, step in enumerate(driver.path):
        if step == landed:
            del driver.path[: index + 1]
            return
    # Landed somewhere the plan does not mention at all - a slide over ground
    # the agent had misremembered. Leave the plan alone: physics refuses the
    # next step if it is no longer a step, and the caller drops the plan then,
    # which is one tick and no guesswork.
    driver.path.pop(0)


def _try_step(
    agent: AgentState, nxt: tuple[int, int], world, rng: random.Random, config: Config
) -> str:
    """Move one cell - or, if something is standing there, hit it instead.

    Bump combat: the agent has no attack command, so a step into an occupied
    tile spends itself as a blow. Returns which of the three happened, because
    the caller has to tell a blow apart from a step: only a step advances the
    plan.

    The diagonal rule matches `pathing._neighbors` and `_wander_ok`. Physics
    has to be at least as strict as the planner, or a plan that legally rounds
    a corner becomes a step that cuts through it.
    """
    dx, dy = nxt[0] - agent.x, nxt[1] - agent.y
    if max(abs(dx), abs(dy)) != 1:
        return BLOCKED
    if not world.tile_at(nxt[0], nxt[1]).passable:
        return BLOCKED
    if dx and dy and not (
        world.tile_at(agent.x + dx, agent.y).passable
        and world.tile_at(agent.x, agent.y + dy).passable
    ):
        return BLOCKED  # no cutting corners past a wall
    entity_at = getattr(world, "entity_at", None)
    monster = None if entity_at is None else entity_at(nxt[0], nxt[1])
    if monster is not None:
        agent_hits_monster(agent.derived, monster, rng, config)
        if monster.hp <= 0:
            _kill(agent, monster, world, rng, config)
        return ATTACKED
    agent.x, agent.y = nxt
    agent.crossed = [nxt, *_slide(agent, dx, dy, world, config)]
    _spring_trap(agent, world, config)
    return MOVED


def _slide(agent: AgentState, dx: int, dy: int, world, config: Config) -> list:
    """Ice carries the agent on in the direction it was already going.

    Returns the tiles it was carried across, because what the agent went over
    matters and not only where it stopped.

    Capped: a slide long enough to cross a frozen hall stops reading as a
    hazard and starts reading as teleportation. Stops early at anything it
    cannot enter, which is what makes ice interesting - the agent plans a
    route and the floor disagrees with the plan.
    """
    crossed: list = []
    for _ in range(max(0, config.ice_slide_max)):
        if not world.tile_at(agent.x, agent.y).slippery:
            return crossed
        ahead = (agent.x + dx, agent.y + dy)
        tile = world.tile_at(*ahead)
        if not tile.passable:
            return crossed
        entity_at = getattr(world, "entity_at", None)
        if entity_at is not None and entity_at(*ahead) is not None:
            return crossed  # slid into something; the collision stops the slide
        agent.x, agent.y = ahead
        crossed.append(ahead)
    return crossed


def _spring_trap(agent: AgentState, world, config: Config) -> None:
    """Stepping on a hidden trap sets it off; a known one is just scenery."""
    trap_at = getattr(world, "trap_at", None)
    if trap_at is None:
        return
    trap = trap_at(agent.x, agent.y)
    if trap is None or not trap.hidden:
        return
    trap.hidden = False
    agent.last_wound = "a trap"
    agent.damage_taken += agent.stats.take(config.trap_damage)
    agent.traps_sprung += 1
    agent.log.record(agent.tick_count, story.sprang_trap(config.trap_damage))
    agent.memory.mark_hazard(
        (agent.x, agent.y), agent.tick_count, world.tile_at(agent.x, agent.y)
    )


def _choke(agent: AgentState, world, config: Config) -> None:
    """Standing in haze costs hit points every tick it is stood in."""
    if config.haze_damage <= 0 or not agent.stats.alive:
        return
    if world.tile_at(agent.x, agent.y).harmful:
        agent.last_wound = "the spores"
        agent.damage_taken += agent.stats.take(config.haze_damage)


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
            agent.log.record(agent.tick_count, story.spotted_trap())
        if not agent.memory.believes_hazard(coord):
            agent.memory.mark_hazard(coord, agent.tick_count, world.tile_at(*coord))


def _kill(agent: AgentState, monster, world, rng: random.Random, config: Config) -> None:
    """Remove a dead monster, maybe leave its belongings, bank the experience."""
    where = (monster.x, monster.y)
    world.remove_entity(monster)
    agent.kills += 1
    agent.life_kills += 1
    agent.log.record(agent.tick_count, story.killed(monster))
    if not agent.stats.alive:
        # The corpse still counts, but a dead agent does not collect on it.
        # Reflected damage can kill a monster with the same blow that killed
        # the agent, and healing or levelling here would lift hp back above
        # zero before _resolve_death looks - quietly cancelling the death and
        # letting a thorns-and-vampiric build live through anything.
        return
    before = agent.stats.level
    ceiling = agent.derived.max_hp if agent.derived is not None else None
    agent.stats.gain_xp(xp_for(monster, config), config, ceiling=ceiling)
    if agent.stats.level > before:
        agent.log.record(agent.tick_count, story.levelled(agent.stats.level))
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
        # Everything it was carrying stays where it fell. The next life can
        # walk back and take it - which is the whole point of memory surviving
        # death, and closes the loop the aquarium is built around.
        for item in [*agent.equipped.values(), *agent.backpack]:
            world.drop_item(item.kind, agent.x, agent.y, item=item)
    agent.equipped = {}
    agent.backpack = []
    agent.grave_sites.add((agent.x, agent.y))
    agent.log.record(agent.tick_count, story.died())
    # The life that just ended, before anything is reset. Held on the agent
    # rather than written here: the tick knows nothing about files, and this
    # module stays runnable headless in a test.
    agent.fallen.append(
        Fallen(
            seed=getattr(world, "seed", 0),
            level=agent.stats.level,
            kills=agent.life_kills,
            depth=agent.life_depth,
            ticks=agent.tick_count - agent.life_started,
            killer=agent.last_wound,
            archetype=archetype(agent.derived, config) if agent.derived else "novice",
            gold=agent.gold,
            name=agent.name,
        )
    )
    agent.life_kills = 0
    agent.life_depth = 0
    agent.life_started = agent.tick_count
    agent.last_wound = "the dark"
    agent.deaths += 1
    # A new life is a new creature, so it gets its own name. Same stream as
    # the first one, keyed on how many have died here.
    agent.name = names.name_for(getattr(world, "seed", 0), agent.deaths)
    agent.stats = Stats.starting(config)
    agent.fleer.stand_down()
    # Whatever it walked over before dying is somewhere else now, and the body
    # is back at the spawn: an unspent skid must not follow it there.
    agent.crossed = []
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
    seen = compute_fov(window, (radius, radius), radius)
    # Lava lights terrain through walls, deliberately. It must not also reveal
    # what is standing in the light: entity sightings feed the threat field,
    # and the agent should not flee a monster it cannot see through rock.
    visible = seen | _lava_glow(window, radius, config)
    observation = {
        (origin_x + lx, origin_y + ly): window[ly][lx] for lx, ly in visible
    }
    in_sight = {
        (origin_x + lx, origin_y + ly) for lx, ly in seen
    }
    entities, items = _things_seen(world, in_sight)
    agent.memory.observe(
        observation, agent.tick_count, entities, items, snapshot_coords=in_sight
    )


def _lava_glow(window, radius: int, config: Config) -> set:
    """Lava lights its own surroundings, whether or not the agent has line of
    sight to them.

    Deep caverns are otherwise a wall of unknown with a red dot in it; letting
    the pools throw light is what makes the far biome look like a place rather
    than a texture. It is generous rather than physical - the glow ignores
    walls within its small radius - and that generosity is the point.
    """
    glow_radius = config.lava_glow_radius
    if glow_radius <= 0:
        return set()
    lit: set = set()
    size = 2 * radius + 1
    for ly in range(size):
        for lx in range(size):
            if window[ly][lx] is not Tile.LAVA:
                continue
            for dy in range(-glow_radius, glow_radius + 1):
                for dx in range(-glow_radius, glow_radius + 1):
                    nx, ny = lx + dx, ly + dy
                    if 0 <= nx < size and 0 <= ny < size:
                        lit.add((nx, ny))
    return lit


def _burn(agent: AgentState, world, config: Config) -> None:
    """Standing next to lava hurts. The deep biome should cost something."""
    if config.lava_heat_damage <= 0 or not agent.stats.alive:
        return
    for dx, dy in DIRS_8:
        if world.tile_at(agent.x + dx, agent.y + dy) is Tile.LAVA:
            agent.last_wound = "the lava"
            agent.heat_damage += agent.stats.take(config.lava_heat_damage)
            agent.damage_taken += config.lava_heat_damage
            return


def _things_seen(world, observation) -> tuple[dict, dict]:
    """Glyphs of whatever stands on the visible tiles, for memory snapshots.

    Worlds that carry no entities (the tiny stubs the tick tests use) simply
    do not offer these lookups, and the agent then remembers terrain alone.
    """
    entity_at = getattr(world, "entity_at", None)
    item_at = getattr(world, "item_at", None)
    shrine_at = getattr(world, "shrine_at", None)
    entities: dict = {}
    items: dict = {}
    if entity_at is None and item_at is None and shrine_at is None:
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
                continue
        if shrine_at is not None:
            # Remembered alongside the loot rather than as its own kind of
            # thing: a totem is scenery the agent can walk to, which is what
            # an item is as far as memory is concerned. It is never returned
            # by `item_at`, so nothing tries to pick one up or plan a robbery
            # around it.
            shrine = shrine_at(*coord)
            if shrine is not None:
                items[coord] = shrine.glyph
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
    damage, reflected_kills = take_turns(
        agent, agent.active_entities, world, rng, config, agent.tick_count
    )
    agent.damage_taken += damage
    for monster in reflected_kills:
        _kill(agent, monster, world, rng, config)


def _think(agent: AgentState, rng: random.Random, config: Config) -> None:
    """Fear first, curiosity second.

    FLEE pre-empts rather than competing on score: a utility comparison would
    let a good enough exploration prospect talk the agent into standing next
    to a troll, and "why is it doing that" should be answerable by looking.
    """
    here = (agent.x, agent.y)
    if agent.fleer.wants_control(
        here, agent.memory, agent.stats, config, agent.derived, agent.tick_count
    ):
        agent.explorer.drop_plan()
        agent.looter.clear()
        if agent.fleer.decide(here, agent.memory, config, agent.tick_count):
            agent.goal_name = "FLEE"
            return
        # Nowhere calmer within reach: fleeing with nowhere to run is not
        # fleeing, it is standing still being afraid. Cornered in a dead end by
        # something it cannot get away from, the agent would otherwise stay
        # pinned for the rest of the run - the release threshold is a fraction
        # of the trigger, so danger it cannot escape never falls far enough to
        # let go. Hand the wheel back and get on with something, and do not ask
        # again for a moment - re-triggering next tick just flickers.
        agent.fleer.stand_down(agent.tick_count + config.flee_cornered_cooldown)
    elif agent.fleer.active:
        # Either the danger passed or the flight timed out; a timed-out flight
        # takes the cooldown so it does not restart on the next tick.
        agent.fleer.stand_down(agent.tick_count + config.flee_cornered_cooldown)
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
