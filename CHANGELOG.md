# Changelog

## Unreleased

### Visitors can see the hall of fame

Press <kbd>h</kbd> on the site to open it and <kbd>h</kbd> again to shut it, or click **hall of fame**. The dead are
fetched when the overlay opens rather than carried on every frame: a life
ends rarely and a frame goes out a dozen times a second to everybody.

A volume mounted at `/data` is used for the hall without any wiring. The dead
are recorded by default now. They shipped switched off, which was
right for a host that wipes its disk on every deploy and wrong everywhere
else — a scoreboard nobody turned on is a scoreboard nobody sees. Point
`CRAWLER_HALL_PATH` at a mounted volume and they outlive deploys as well.

The viewer count and the source link moved to the corner of the window. The
panel is about the creature; neither of those is.

### Sized for a box with a core to spend

The window is 120×44 at twelve frames a second, up from 104×36 at eight. The
old numbers were shaped by a free tier metered at a tenth of a core; a frame
that size costs about 25ms to build, so this is roughly a third of one.

### An amulet on the ice could end a run

Picking things up read only the tile the agent finished its move on, and a
slide finishes further along than it started. So loot lying on a drift could
not be stood on at all: the agent planned onto it, the ice carried it past,
and it planned onto it again. One run spent sixteen thousand ticks on a
single amulet, with 166 tiles explored.

A slide now collects what it crosses. Refusing to go for unreachable loot
would also have fixed it, and would have been the worse answer - skidding
across the ice and coming away with something is what the terrain should feel
like.

### The same creature kept turning up

Not the name generator - it makes a thousand distinct names in a thousand
tries. The hosted version opened on a fixed seed and then walked seed + 1 per
death, so every restart replayed the same procession of worlds, and a free
instance that sleeps between visitors restarts constantly. Anyone dropping in
kept meeting the third creature of that sequence by name.

The instance now opens on a world nobody has seen and logs which, and each
death draws a world this session has not visited rather than the one next
door. `CRAWLER_SEED` still pins it, and pinning reproduces the whole
procession, not just the first world - the later ones are drawn from a stream
seeded by the first.

### Fixed after review

- **Three menu screens had holes in their titles.** The block alphabet only
  covered the letters in "CRAWLER", and unknown letters fall back to blanks -
  so SETTINGS read "SE  I  S", SOAK read "S A " and HALL read " ALL". The
  alphabet is now complete, with digits, and a test renders every title and
  fails on a gap.
- **A cleared themed chunk refilled with the wrong monsters.** Initial
  population honoured the biome's bestiary and respawning did not, so a
  derelict station stayed a station only until the agent had killed what was
  in it, then started producing rats.
- **Ice and fog could not be spawned on.** Spawning asked for FLOOR, which
  stopped meaning "walkable" when those arrived - about a sixth of a spore
  chunk was ineligible for any monster, item or trap.
- **One stuck viewer froze the web for everyone.** Frames were sent to
  viewers one after another with no deadline, and a send does not fail when a
  client stops reading - it waits for the transport, which is minutes. Sends
  are concurrent and deadlined now; a viewer who cannot take a frame misses
  it and is dropped.
- **The browser leaked a keep-alive timer per reconnect**, so a tab left open
  through a few network hiccups sent its keep-alive several times over.
- **"a orc".** Death causes pick their own article now.

### Everything down there has a name now

The creature is born with one, the HUD says it above everything else, and the
hall of fame records who it was rather than just what it managed.

Names are built from syllables in five styles, each with its own consonants,
vowels, endings and surnames - so Thalinel Moonweaver, Brokk Ironfoot and
Snikdug Scarcrusher cannot come out of the same bag. Roughly 59,000 distinct
names in 60,000 rolls, and every one of them pronounceable: a name has to get
past a check for consonant pile-ups, vowel puddles and stutters before it is
handed out, and anything that fails is redrawn.

A new life is a new creature with a new name. The name is drawn from its own
seeded stream, so adding all this did not move a single tile of terrain.

### It runs in a browser now

`web/` serves the same aquarium over a WebSocket: the server ticks one world
and every visitor watches it. Nobody plays this, so there is nothing to keep
separate per person — one simulation, one serialized frame, every socket. It
ticks only while somebody is looking.

Not a port and not a second copy of the game. The frame the browser paints is
built by the same code the desktop window uses, which is now `render/frame.py`
— pulled out of `main.py` so that a headless server can build a picture
without pygame anywhere in the process.

A frame that fails now costs a frame rather than the aquarium. One loop feeds
every viewer, so an exception in it ended the task and left everybody looking
at a frozen picture - with the sockets still open and the health check still
saying yes. Failures are logged, counted and backed off, and `/healthz`
answers 503 when the loop behind it has stopped, so a host that restarts on a
failed check gets the chance to.

The hosted version rolls a fresh world when the creature dies. On the desktop
the default is to stay put, so the next life can walk back for its own gear;
watching a stream, a death is the end of a story and the interesting thing is
a new one somewhere else. `CRAWLER_NEW_WORLD_ON_DEATH=0` restores the old
behaviour.

The side panel carries what the agent is wearing, between the stats and the
log, the way the desktop HUD always has - cursed gear in red.

The page scales the map to the window it is drawn in. The first version sized
cells off the available width alone, so on a maximised browser the grid came
out taller than the screen and the bottom third of the dungeon was below the
fold. Both axes are considered now, and the window is shaped for widescreen.

Deploy with the included `render.yaml` (Render blueprint) or `Procfile`, and
run it locally with `run-web.bat`.

### Faster

- **Biomes are looked up once per chunk, not once per tile.** The renderer
  asked which biome every visible tile was in, every frame — thousands of
  repeats of the same region-noise arithmetic for tiles that share a chunk.
  A chunk's biome is fixed the moment its coordinates are, so it is cached:
  about a quarter off the cost of drawing a frame, desktop and web alike.

### Twelve new biomes

The world had three faces; it now has fifteen, and it no longer picks between
them by distance. A low-frequency region noise chooses the theme while
distance keeps its old job of setting danger and loot — so how far the agent
has walked no longer tells you what it is walking through.

New places: the ashfields, the ossuary, fungal warren, overgrown ruins, rust
marsh, crystal hollows, the frozen deep, spore hollows, the sunken cathedral,
derelict station, machine halls, and the weave.

Five new generators arrived with them — eroded ruins, gridded stations with
doors that do not all open, braided mazes, causeways over deep water, and
regular lattices with pieces missing.

### Two new kinds of ground

- **Ice** carries the agent on past where it meant to stop.
- **Haze** is walkable and hurts, so routes price it as a detour rather than
  refusing it.

### The agent understands ice now

Sliding used to be something that happened *to* the plan: the agent stepped,
the floor carried it somewhere else, and it re-planned. Ice was priced as a
penalty and the agent crept along the rock beside a frozen hall.

A slide takes one tick however far it runs, which makes ice the fastest ground
in the game if you can aim it. The pathfinder now searches over the tile a
step actually *ends* on rather than the neighbour it enters, so frozen halls
get used as fast travel. Cost is charged in ticks rather than tiles, and the
only surcharge left on ice is for finishing a move on it.

Ground a slide crosses counts as explored, too. Nothing can stop in the
middle of a drift, so a frontier tile stranded there used to be unreachable
forever — the explorer wrote off the whole neighbourhood and went back to
wandering. The agent sees those tiles go past, which is all exploring one
means, so routes now report them.

Across sixteen worlds of 4,000 ticks, the agent reaches 618 tiles from spawn
instead of 380, kills more (824 vs 730), and never runs out of places to go.

### The HUD names where you are

A `biome` line under `build` and `goal`, in that biome's own colour — pale
blue in the frozen deep, green in the fungal warren.

### Fixed

- **Config knobs that no route could feel.** `haze_step_cost` shipped dead:
  the field existed, the pathfinder had a parameter for it, and nothing
  connected the two, so every route in the game was planned on hardcoded
  defaults. Costs now travel from the config to the planner, and a test pins
  the handover rather than the number.
- **The frozen deep could strand the agent.** Long slides invalidated a plan
  faster than the agent could make one, so it re-planned in place forever: one
  world reached 16 tiles in 4,000 ticks and killed nothing. Slides are shorter
  now and ice costs a little to cross — the same world reaches 237 tiles and
  kills 33.

## 0.1.0 — 10 September 2026

First release. An autonomous `@` explores an endless dungeon while you watch.
Nobody plays it.

### The world

- **It never ends.** The dungeon streams in as the agent walks and is never
  thrown away, so anywhere it has been is still there if it goes back.
- **Three regions, and they look it.** Warm quarried stone near the start,
  cold blue-grey caves further out, and a bruised violet dark in the deep
  caverns, with water and lava pools. The regions blend into one another, so
  walking outward looks like walking outward.
- **Same seed, same world, forever.** Press `n` for a new one.

### The creature

- **It runs on memory, not facts.** It acts on what it remembers seeing, which
  means it can be wrong — and being wrong is where the interesting behaviour
  comes from. It will flee a troll that wandered off ten minutes ago and walk
  into one that arrived after it looked away.
- **It forgets.** Old knowledge expires, so ground it has forgotten becomes
  worth exploring again. The dungeon never runs out of novelty because the
  agent keeps losing it.
- **It explores, fights, flees, loots and levels.** Rats through dragons, each
  a different colour so you can read the danger before you read the letter.
- **It dies, and starts again.** Level 1, full health, all its memories — and
  its gear still lying where it fell, next to its own grave. It can walk back
  and take it.
- **It has taste in equipment.** Items roll rarities and affixes, and the good
  ones do not just add numbers: a *farsighted* ring widens what it can see, a
  *craven* one makes it panic sooner, a *curious* one makes it value the
  unknown more. Gear changes how the creature behaves, not just how hard it
  hits.
- **Traps.** It spots them, remembers them, and steps around them when there is
  room to — but a known trap is an inconvenience, not a wall, so it will walk
  over one rather than give up on everything beyond it.

### Watching it

- **A title screen** with block-letter art. `esc` from the world goes back to
  it, and the creature keeps running while it is up, so *resume* resumes.
- **A resizable window**, `F10` for a borderless window and `F11` for
  borderless fullscreen. Both land on the monitor the window was already on,
  centred, rather than jumping to the primary one - the monitor layout comes
  from the operating system, so monitors to the left of the primary one (which
  live at negative coordinates) work like any other. Borderless
  windows can still be resized. Making the window bigger shows more of the
  dungeon rather than magnifying it.
- **A HUD** with health, level, current goal, what it is wearing, and a rolling
  log of what just happened: *killed the rat*, *found a cruel sword*, *stepped
  in a trap*, *died in the dark*.
- **A hall of fame.** Every life the creature has lived, best first: how far it
  got, what it had become, and what finally killed it. *level 6, 140 kills, 820
  deep - a troll.* Ranked by a score that counts depth for more than levels,
  because a level 9 that never left the first ring is a lesser run than a
  modest one that reached the deep caverns.
- **Press `b` to see the bag** - not just how many spares it is carrying, but
  what each one would change if it wore it, so you can see why it does not.
  Better loot reads brighter.
- **Five overlays** (`F1`–`F5`) that answer "why is it doing that?" by drawing
  what the agent *believes* rather than what is true: what it can see, how
  stale its memory is, where it thinks danger is, what it plans to walk, and
  where it still hopes to find something.
- **Pause and speed** — `space`, then `1`/`2`/`3` for 1x, 4x, 16x. 16x is the
  same simulation run faster, not a different one.
- **Screenshots** with `p`.
- **`run.bat`** — double-click and it starts.

### Settings

- **A settings screen** on the title menu: soak workers, starting speed, what
  happens on death, how strongly the biome tints the ground, and moss on or
  off. Settings are remembered between runs.
- **On death, keep the world or roll a new one.** Keeping it is the default:
  the creature starts again knowing where it has been, with its gear still
  lying where it fell.
- **Soak from the menu**, without a terminal. It runs one world per core and
  flags in red any world where the agent stalled or ran out of places to go.

### Under the hood

- 368 tests, plus a 100,000-tick soak run that checks the thing can be left
  running: no crashes, memory that stays bounded, and an agent that keeps
  finding somewhere to go.
- Everything below the renderer is headless and testable; every tunable lives
  in one file (`config.py`), including the weights that decide what the
  creature considers good gear — change those and it grows into something
  different.

### Fixed along the way

Things found by profiling, by a code review, and by watching long runs:

- Worn equipment did not affect combat at all. The whole loot system was
  decorative in a fight; now a better sword actually hits harder.
- Levelling up could *wound* an agent in good armour.
- The agent could stop exploring entirely and stand still for the rest of a
  run — twice, for two different reasons. Both fixed, both now watched for.
- A monster killed by spiked armour paid no experience and dropped nothing.
- Long runs got slower and slower as the agent remembered more. The agent now
  keeps track of where its frontier is instead of re-deriving it from scratch
  every time it thinks, which was the largest single cost in a long run.
- **Soaking many worlds at once**, one per core: 8 worlds took 70 seconds on
  one worker and 15 on eight, with identical results.
- Long item names ran off the edge of the screen. They wrap.
