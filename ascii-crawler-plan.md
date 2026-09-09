# AsciiCrawler — Plan

> **Status:** Planning
> **Last Updated:** 2026-09-09

---

## Vision

An ambient "algorithm aquarium": a `@` autonomously explores an infinite, procedurally generated ASCII dungeon in a window that looks like a terminal. No player input into the agent — the intelligence is the show. The agent sees via field-of-view, remembers what it saw (and *forgets* it over time), and picks goals with a utility function that weighs curiosity, loot, threat, and survival. It fights, flees, loots, equips, dies, leaves a gravestone, and respawns weaker but wiser. Fast-forward and debug overlays let you watch the AI think.

Visual touchstones: original Rogue, classic Dwarf Fortress.

## Decision Matrix (locked)

| Decision | Choice |
|---|---|
| Human role | Pure observer (aquarium) |
| Run objective | None — endless wandering |
| World contents | Items, hazards (traps), monsters |
| Display | GUI window that looks like a terminal (pygame) |
| World size | Infinite, streaming chunk generation |
| Agent memory | Finite, sliding window with time-based decay (forgetting) |
| Mortality | Mortal; gravestone persists; respawn keeps memory, resets stats/inventory |
| Combat | Utility fight-or-flight, bump-to-attack |
| AI architecture | Utility scoring for goal selection |
| Stack | Python 3.12+, pygame, numpy |
| World persistence | Chunks persist in RAM forever; entities simulate only near the agent |
| Fog of war | Coupled to memory — the screen *is* the agent's mind; forgotten tiles go blank |
| Progression | Full inventory, XP levels, distance-scaled threat |
| Build system | Emergent: loadout evaluator with synergy terms; HUD retro-labels archetypes (cosmetic only) |
| Loot depth | Affix system: stat mods, trigger effects, curses, cognition mods; rarity tiers by distance |
| Generation | Biomes by distance from spawn: BSP rooms → cellular caves → caverns |
| Pacing | ~10 ticks/sec base, 1x/4x/16x speeds, pause, full debug overlays |

## Architecture

```
ascii-crawler/
├── main.py              # wiring, game loop, controls
├── config.py            # all tunables: weights, radii, decay, speeds (dataclasses)
├── world/
│   ├── chunks.py        # chunk store, streaming, seam-safe generation
│   ├── gen_bsp.py       # rooms + corridors (near-spawn biome)
│   ├── gen_cave.py      # cellular automata (mid biome)
│   ├── gen_cavern.py    # large caverns + liquid pools (far biome)
│   └── populate.py      # per-chunk monster/item/trap spawning, distance scaling
├── agent/
│   ├── fov.py           # recursive shadowcasting (symmetric, radius ~8)
│   ├── memory.py        # sparse tile memory, timestamps, decay/pruning
│   ├── goals.py         # utility scoring: EXPLORE / LOOT / FIGHT / FLEE / REST
│   ├── loadout.py       # loadout evaluator: item scoring, synergy terms, equip decisions
│   └── pathing.py       # A* over known-traversable tiles
├── sim/
│   ├── tick.py          # scheduler (speed-based entity turns)
│   ├── monsters.py      # monster table + simple AI (wander/chase within activation)
│   ├── combat.py        # bump combat, damage calc, death/respawn/graves
│   └── items.py         # item table, inventory, equipment, potions, XP/levels
├── render/
│   ├── screen.py        # pygame window, glyph grid, camera follow
│   ├── fog.py           # brightness tiers driven directly by memory age
│   ├── hud.py           # stats, goal, inventory summary, tick/death/kill counters
│   └── overlays.py      # F-key debug layers (see Debug Overlays)
└── tests/               # headless: gen determinism, FOV symmetry, A*, utility edges
```

Core separation rule: **everything under `world/`, `agent/`, `sim/` is pygame-free and unit-testable headless.** `render/` only reads state.

## Subsystems

### 1. Streaming world generation

- **Chunks:** 64×64 tiles, keyed `(cx, cy)` in a dict. Generated lazily when the agent comes within 2 chunks of a missing one. Never discarded.
- **Seams:** each chunk, when generated, drills a corridor from its center toward the midpoint of each shared edge with its 4 neighbors. Neighbors drill the mirror corridor when they generate, so both halves meet at the edge deterministically — no cross-chunk state needed. Corridor paths are L-shaped with jitter seeded by `hash(world_seed, cx, cy)` so both sides agree.
- **Determinism:** per-chunk RNG seeded `(world_seed, cx, cy)`. Same world, same chunks, forever.
- **Interior connectivity:** post-pass flood-fills from chunk center; any unreachable pocket gets drilled into the main cavity.
- **Biomes by distance** (blended with noise at band edges so there are no hard rings):
  - 0–150 tiles: BSP rooms + corridors (Rogue heartland)
  - 150–400: cellular-automata caves
  - 400+: large-radius CA caverns, with water/lava pools
- **Tiles:** `WALL`, `FLOOR`, `WATER` (impassable), `LAVA` (impassable). Keep the set tiny.

### 2. Population & threat scaling

- Spawned per chunk at generation from the chunk's seeded RNG. Density and monster tier scale with distance from spawn.
- Monster table (draft): rat `r`, goblin `g`, orc `o`, ogre `O`, troll `T`, dragon `D` — each with HP/ATK/speed/threat. Deep biomes roll deeper tables.
- Item table: weapons `)`, armor `[`, rings `=`, amulets `"`, potion `!` (heal), gold `$` (score flavor) — generated via the affix model in §6.
- Traps `^`: hidden until detected (revealed when in FOV within 2 tiles, or on trigger) — damage on trigger.
- Monster respawn: slow cooldown per chunk (capped per chunk), so the world stays alive behind the agent.
- Items roll base type + tier + rarity + affixes (see §6); deeper biomes roll deeper tiers and better rarity odds.

### 3. Perception — field of view

- **Recursive shadowcasting**, 8 octants, symmetric, radius 8. (This replaces the original "raycasting" idea — shadowcasting is the grid-native equivalent with no per-ray artifacts.)
- Output: visible tile set + entities within it. This is the *only* channel between world truth and agent belief.

### 4. Memory — the signature system

- Sparse dict keyed by tile coord → `{terrain_belief, last_seen_tick, last_entity_snapshot, last_item}`. Only tiles the agent has seen exist in it.
- **Decay:** knowledge expires after `MEMORY_TTL` ticks (start: 3000 ≈ 5 min at 1x). Pruner job drops expired entries periodically.
- **Coupled rendering:** the fog *is* memory — visible = full color; fresh memory = ~60% brightness; stale = ~35%; expired = blank. Remembered entities draw dim/ghost-colored at their last-seen position. You watch the agent's mind work and fade.
- Agent plans entirely on belief. Stale monster memories are how it gets ambushed — that's a feature.

### 5. Decision — utility AI

Every decision tick (throttled: on event, or every ~5 ticks), score candidate goals and take the max:

| Goal | Score (sketch) | Notes |
|---|---|---|
| EXPLORE | `w_explore · info_gain / (1 + path_cost)` | Frontier tiles = known floor adjacent to unknown/forgotten. Sample nearest ~50 to keep it cheap. Path via A* over *known* passable tiles only. |
| LOOT | `w_loot · upgrade_delta / (1 + path_cost)` | `upgrade_delta` = loadout score gain if equipped (see §6) — not the item's raw stats. |
| FIGHT | `w_fight · win_probability / (1 + cost)` | Win prob from HP/ATK/DEF vs remembered monster stats. |
| REST | `w_rest · (1 - hp_frac)` when hurt | Path to nearest remembered-safe tile, wait; slow passive regen. |
| FLEE | override, not scored | When a visible threat outclasses the agent: maximize distance over known tiles toward remembered safe ground. |

- Threat field: remembered monster positions project repulsion into nearby frontier scores.
- Hysteresis: incumbent goal gets a stickiness bonus; small noise on all scores. Anti-dither, anti-loop.
- All weights live in `config.py` as one dataclass — tuning is a first-class activity.
- Auto-equip on pickup when strictly better; potions auto-considered during REST.

### 6. Items, perks & emergent builds

The agent never "theorycrafts" — builds are whatever the loadout evaluator's argmax is. Coherence emerges from synergy terms.

**Item model.** Item = base type (weapon/armor/ring/amulet) + tier (distance-scaled) + rarity roll (common/uncommon/rare/epic → 0–3 affixes) + affixes drawn from seeded pools. Potions and gold stay outside the affix system.

**Affix kinds.**
- *Stat mods:* flat and percent (`ATK+2`, `HP+20%`).
- *Triggers:* event-driven effects — on-kill heal, damage shield on hit-taken, first-strike bonus, low-HP rage. Sim emits events (`kill`, `hit_taken`, `hit_dealt`, `step`, `equip`); triggers subscribe.
- *Curses:* negative modifiers (`ATK+4 but vision −1`) that reduce evaluator score but can be outbid by synergy — risk-reward decisions emerge.
- *Cognition mods:* perks touching `vision_radius`, `memory_TTL ±%`, move speed, regen rate, trap-detection radius. This toy's gear changes how the agent *thinks*, not just how hard it hits — a `Phantom`-flavored ring literally lets it see and remember more. Applied as derived-stat recalculation whenever the loadout changes.

**Loadout evaluator (`agent/loadout.py`).**
- `score_loadout(equipped, context) = Σ item power + Σ stat interactions + Σ synergy terms`, with context = current HP, threat environment, memory state.
- Synergy terms come from a small hand-authored table (~10 keyword pairs: crit×crit, lifesteal×high-ATK, vision×memory-TTL, ...). This table is the engine that makes builds emerge.
- Equipment: fixed slots (weapon, armor, ring ×2, amulet) + 6-slot backpack for spares. Owned ≤11 items → brute-force all slot assignments (~hundreds of combos, trivial). Re-evaluate on pickup, rest, and any loadout change; auto-equip strictly better sets, carry near-equal alternatives in the pack.
- The LOOT goal prices items by `upgrade_delta` (best achievable loadout delta), which is how "build understanding" actually enters the brain.

**HUD labels (cosmetic).** A handful of archetype definitions (name + keyword vector, e.g. Berserker, Juggernaut, Phantom, Warlock). The HUD displays the closest match by similarity ("Build: Phantom 74%"). The agent never reads these — zero behavioral effect, pure flavor for the observer.

**Death interaction.** Build identity dies with the gear (dropped at the gravestone); the evaluator is stateless beyond current inventory. Every life re-rolls a build trajectory from what the world offers. (Past graves are lootable — Phase 7's full-circle moment.)

### 7. Simulation scope & scheduling

- Tick scheduler: entities act on speed (agent: every tick; ogre: every 2nd; dragon slower but brutal).
- **Activation radius (~40 tiles):** monsters/items inside simulate; outside they're frozen in RAM. Classic roguelike dormancy.
- Combat: bump-to-attack, one hit per action, `dmg = ATK - DEF ± variance`. Kills → XP → levels (+HP/+ATK).
- **Death:** drop inventory on tile, place gravestone `†` (fallback `+` if the font lacks it), respawn at spawn or safest known tile. Stats and inventory reset; **memory persists** — weaker but wiser.

### 8. Rendering & controls

- pygame window ~1200×800, bundled monospace TTF (ship one — don't trust system fonts, e.g. DejaVu Sans Mono or IBM Plex Mono).
- Camera follows the `@`. No smoothing needed at ASCII fidelity; direct follow is crisper.
- HUD strip: HP, level/XP, ATK/DEF, goal + current utility, build label (e.g. "Phantom 74%"), inventory summary, kills, deaths, tick count, speed.
- **Debug overlays** (F1–F5): frontier highlights + scores; current goal marker + planned A* path; threat field heatmap; memory-age heatmap; chunk boundaries + activation radius.
- Controls: `SPACE` pause · `1`/`2`/`3` = 1x/4x/16x · `F1–F5` overlays · `R` new seed · `ESC` quit.
- Fast-forward: run N sim ticks per frame; at 16x render every 4th tick.

### 9. Performance

10 TPS × trivial grid ops = nothing. The two real costs: A* per decision (bounded by frontier sampling + throttled decisions) and unbounded growth (memory pruner bounds the dict; chunk dict grows ~1 per couple minutes of exploring — hours of runtime is a few thousand chunks, fine in RAM).

## Key Decisions & Hardest Problems

1. **Chunk seams** are the #1 bug farm. Mitigation: deterministic edge-midpoint connection scheme + an integration test that walks every border of adjacent generated chunks and asserts mutual passability.
2. **Memory-forgetting is load-bearing.** Without decay, an endless agent runs out of things to care about. Decay recycles the world into novelty — this is why "infinite + finite memory" was the right call.
3. **Utility dithering** will happen; hysteresis + noise + throttled decisions are the controls. Overlays make it visible when it does.
4. **Belief vs truth separation** must be absolute: the agent never reads world state directly, only memory. This is the difference between an explorer and a cheat, and it's what makes mistakes (ambushes on stale info) legible and fun.
5. **Tuning is content.** All weights in one config dataclass; overlays exist so tuning sessions are visual.
6. **Builds are emergent, never authored.** The agent scores loadouts with a synergy-aware evaluator and takes the argmax; archetype names are HUD-only decoration. This keeps the brain honest (no hidden scripted preferences) and the combinatorics bounded (≤11 items → brute-force is exact and cheap). The synergy table is where build *flavor* lives — tune it like the utility weights.

## Phased Build

### Phase 0 — Skeleton
- [ ] Project scaffold, config dataclass, pygame window with glyph grid + bundled font
- [ ] Hardcoded map, `@` walks randomly, camera follow, 10 TPS loop

### Phase 1 — The Look (finite world)
- [ ] BSP generator (single map), tiles + rendering, colors
- [ ] Recursive shadowcasting FOV, symmetric, tested
- [ ] Fog of war: visible / remembered / unseen brightness tiers

### Phase 2 — The Explorer (finite world)
- [ ] Sparse memory map with timestamps
- [ ] Frontier enumeration + A* over known tiles
- [ ] EXPLORE utility goal → the toy first works: watch it clear a finite dungeon
- [ ] Headless sim harness (run N ticks, log coverage stats)

### Phase 3 — The Infinite World
- [ ] Chunk store, streaming, lazy generation, seam-safe corridors + border integration test
- [ ] Cave + cavern biome generators, distance blending
- [ ] Populate with distance scaling; persistent world, activation radius dormancy
- [ ] Memory decay + pruner + coupled fog fade (tiles go blank again)

### Phase 4 — Danger
- [ ] Monster table, dormant AI (wander/chase), speed scheduler
- [ ] Bump combat, damage calc, threat estimation
- [ ] FLEE override + threat field in utility scores
- [ ] Death: graves, drops, respawn (memory persists, stats reset)
- [ ] Traps: hidden, detection, damage
- [ ] XP, levels, stat growth

### Phase 5 — Loot, Inventory & Builds
- [ ] Item model: bases, tiers, rarity, affix pools (stats / triggers / curses / cognition mods)
- [ ] Perk event hooks in sim (`kill`, `hit_taken`, `hit_dealt`, `step`, `equip`) + derived-stat recalc on loadout change
- [ ] Loadout evaluator + synergy table (`agent/loadout.py`); brute-force slot assignment over owned items
- [ ] Equipment slots + 6-slot backpack; auto-equip on strict improvement; carry near-equal spares
- [ ] LOOT goal priced by `upgrade_delta`; REST/potion interplay
- [ ] HUD build label (archetype keyword vectors, cosmetic)
- [ ] Monster respawn cooldowns per chunk

### Phase 6 — The Aquarium Polish
- [ ] HUD (stats, goal, utility, counters)
- [ ] All debug overlays F1–F5
- [ ] Pause + 1x/4x/16x speed controls
- [ ] New-seed restart, screenshot key
- [ ] Tuning pass on all weights; soak test (100k ticks headless, no crash, sane stats)

### Phase 7 — Stretch
- [ ] Remembered-entity ghost rendering refinements
- [ ] Water/lava pools as vision/melee flavor in deep biomes
- [ ] Grave-robbing its own past corpses for dropped gear (full circle)
- [ ] Ambient flourishes: vermin `~`, moss, flavor logs

## Testing Strategy

- All core logic headless and pytest-able (no pygame import below `render/`).
- Gen determinism: same seed → identical chunks (hash the tile arrays).
- FOV symmetry: for sampled tile pairs, visible-from-A⇔visible-from-B.
- Seam integration: adjacent chunks mutually passable at every shared-edge connection.
- A* correctness/admissibility on hand-built mazes; utility edge cases (flee overrides, hysteresis stability).
- Loadout evaluator: synergy ordering (whole > sum of parts), curse outbid by synergy, cognition mods correctly recalc derived stats, brute-force search finds known-optimal assignments on fixed fixtures.
- Affix generation determinism: same chunk seed → same items.
- Soak: 100k-tick headless run asserting no exceptions, bounded memory, non-zero frontier progress.
