# AsciiCrawler

An autonomous `@` in an infinite dungeon. Nobody plays it — you watch it.

The agent explores, fights, flees, loots, levels, dies, and starts again. It
runs on beliefs rather than facts: it acts on what it remembers seeing, which
means it can be wrong, and being wrong is where the interesting behaviour comes
from. It will flee a troll that wandered off ten minutes ago, walk into one
that arrived after it looked away, and re-explore ground it has forgotten.

```
python main.py
```

## Controls

| key | |
|---|---|
| `esc` | quit |
| `space` | pause |
| `1` `2` `3` | speed 1x / 4x / 16x |
| `F1`–`F5` | overlays: fov, memory age, threat, plan, frontier |
| `h` | toggle HUD |
| `n` | new world (fresh seed, fresh creature) |
| `p` | screenshot |

The overlays are the interesting part: they answer "why is it doing that?" by
drawing what the agent *believes* rather than what is true.

## How it is put together

```
world/   terrain, chunks, population   — no pygame
agent/   memory, pathing, goals, gear  — no pygame, reads memory only
sim/     the tick, combat, AI, items   — no pygame
render/  fog, HUD, overlays, screen    — reads handed state only
```

Three rules hold the design together:

**Belief before truth.** The agent's brain reads `agent/memory.py` and nothing
else. FOV is the only channel from the world into memory. Monsters, by
contrast, read the world directly — they are the hazard the character has
beliefs *about*, not characters with beliefs.

**Memory is mortal.** Knowledge expires after `memory_ttl` ticks and a pruner
drops it. That bounds the belief store over an unbounded run, and it means
forgotten ground returns to the frontier — the world never runs out of novelty
because the agent keeps losing it. Death resets the body but never the mind:
the creature starts again at level 1 knowing where it has been, and its gear is
still lying where it fell, next to its own grave.

**Determinism everywhere.** Same seed, same world, forever. Chunks, spawns,
affixes and respawns each roll from their own seeded stream, so retuning loot
cannot shift a single tile of terrain.

## The world

Chunks of 64×64 stream in as the agent approaches and are never discarded.
Biomes go by distance from the origin — rooms and corridors near home,
cellular-automata caves further out, then large caverns with water and lava,
blended at the edges so there are no rings. Chunks drill their seam corridors
from their own seed alone, so neighbours agree at the border with no shared
state.

## Tests

```
pytest              # the suite
pytest -m slow      # the 100k-tick soak (minutes)
```

Everything below `render/` is headless and pygame-free. The soak asserts the
three things only a long run can break: no exceptions, bounded memory, and an
agent that keeps finding somewhere to go.

## Tuning

Every knob lives in `config.py` as one frozen dataclass — biome bands, spawn
densities, memory TTL, fog brightness, the loadout weights that decide what the
creature *wants*. Changing the `v_*` weights changes what it considers good
gear, and therefore what it becomes.
