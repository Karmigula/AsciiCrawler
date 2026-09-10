# AsciiCrawler

An autonomous `@` in an infinite dungeon. Nobody plays it — you watch it.

<img width="1200" height="800" alt="python_n9lhxMAZDv" src="https://github.com/user-attachments/assets/e9e3504d-daf6-4c2f-ac8c-42bbd1a23f97" />

The agent explores, fights, flees, loots, levels, dies, and starts again. It
runs on beliefs rather than facts: it acts on what it remembers seeing, which
means it can be wrong, and being wrong is where the interesting behaviour comes
from. It will flee a troll that wandered off ten minutes ago, walk into one
that arrived after it looked away, and re-explore ground it has forgotten.

It opens on a title screen. The window is resizable — a bigger window shows
more world rather than a magnified slice of it.

Double-click `run.bat`, or:

```
.venv\Scripts\python.exe main.py
```

First time, from a fresh clone:

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Python 3.10 or newer. The game itself needs two packages: **pygame-ce** and
numpy — note the `-ce`, since plain `pygame` is a rival fork that installs a
module by the same name and the two do not belong in one environment.
`requirements.txt` also carries uvicorn, which nothing imports yet.

## Watching it in a browser

There is a hosted version of the same game in `web/`. It is not a port: the
server runs the identical simulation and the identical frame builder, and
sends the finished picture down a WebSocket for the page to paint.

```
.venv\Scripts\python.exe -m uvicorn web.app:app --port 8000
```

Then open <http://127.0.0.1:8000>, or double-click `run-web.bat`.

**Everyone watches the same world.** Nobody plays AsciiCrawler, so there is no
input to keep separate per visitor and no reason to run a world each — one
simulation feeds every socket, and the same serialized frame goes to all of
them. It only ticks while somebody has the page open, so an empty room costs
nothing.

| variable | | default |
| --- | --- | --: |
| `CRAWLER_COLS` / `CRAWLER_ROWS` | size of the window | 104 × 36 |
| `CRAWLER_FPS` | frames a second to aim for | 8 |
| `CRAWLER_WORLD_TICKS` | roll a fresh world after this many ticks | 40,000 |
| `CRAWLER_SEED` | which world to start on | config default |
| `CRAWLER_HUD_CHARS` | width the side panel is clipped to | 46 |
| `CRAWLER_NEW_WORLD_ON_DEATH` | `0` to stay in the same dungeon after a death | on |
| `CRAWLER_HALL` | `1` to write the hall of fame to disk | off |

The page scales the grid to whatever room the browser gives it, so the same
frame fits a phone and a 1440p window. Everyone shares one frame, so the
*number* of cells is fixed by the server and the page can only draw them
larger or smaller — 104 × 36 draws at roughly 16:9, which fills a maximised
window rather than leaving bands down both sides.

A small host will not always hit the frame rate. That is fine — falling
behind makes the tank run slower, not wrong.

### Deploying it

`render.yaml` is a Render blueprint: **New → Blueprint**, point it at the
repo, done. `Procfile` covers hosts that want one instead. The start command
either way is:

```
uvicorn web.app:app --host 0.0.0.0 --port $PORT
```

Render's free instance sleeps after a spell without traffic and wakes on the
next request, which suits something nobody is obliged to watch. For a custom
domain, point a subdomain at it rather than the apex — `crawl.yourdomain.com`
keeps the rest of the domain free to move.

See [CHANGELOG.md](CHANGELOG.md) for what is in this release.

## Controls

| key | |
|---|---|
| `esc` | back to the title screen (again to quit) |
| `space` | pause |
| `1` `2` `3` | speed 1x / 4x / 16x |
| `F1`–`F5` | overlays: fov, memory age, threat, plan, frontier |
| `b` | show the bag |
| `h` | toggle HUD |
| `n` | new world (fresh seed, fresh creature) |
| `p` | screenshot |
| `F10` | borderless window |
| menu | settings, a soak you can run without a terminal, and the hall of fame |
| `F11` | borderless fullscreen (fills the screen it is on) |

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
Chunks drill their seam corridors from their own seed alone, so neighbours
agree at the border with no shared state.

Fifteen biomes, chosen by **region noise** rather than by distance. Distance
still sets how dangerous a place is and how good the loot gets; noise decides
what it *looks* like. So the character of the world stops being a function of
how far the agent has walked — there are no rings, and no two runs read the
same:

| | | |
|---|---|---|
| quarried halls | wet caves | deep caverns |
| the ashfields | the ossuary | fungal warren |
| overgrown ruins | rust marsh | crystal hollows |
| the frozen deep | spore hollows | the sunken cathedral |
| derelict station | machine halls | the weave |

Eight generators back them: rooms, caves, caverns, eroded ruins, gridded
stations, braided mazes, flooded causeways, and lattices. Two terrain types
came with them — **ice**, which carries you on past where you meant to stop,
and **haze**, which is walkable and costs hit points, so a plan prices it as
a detour rather than refusing it.

The HUD names the biome the agent is standing in, under the build and goal
lines, tinted with that biome's own colour.

**The agent plans ice as physics, not as a penalty.** A slide happens inside
a single tick however far it runs, so a frozen hall is fast travel that is
hard to aim — and the pathfinder searches over *landing* tiles rather than
neighbours, which makes it use the ice instead of creeping along the rock
beside it. The cost of a step is charged in ticks, and the only surcharge on
ice is for *ending* a move there, since the next move from a drift is at the
mercy of the same physics.

## Soaking many worlds at once

One world runs on one core - the tick is sequential Python, and threads would
share a core's worth of bytecode. Many *worlds* are perfectly independent, so
that is where a big CPU pays:

```
python -m sim.soak 2000 8 8      # ticks, worlds, workers
```

Measured on a 24-core machine: 8 worlds x 3000 ticks took 70s on one worker
and 15s on eight, with identical results.

The worker count set in the settings screen is saved to `settings.json` and is
what this command uses by default. The same screen can run a soak itself, if
you would rather not use a terminal.

More worlds is about coverage, not speed. The last real bug here was found by
soaking eight seeds at once: two of them were starved for most of their run
while the single seed I had been testing looked perfectly healthy.

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
