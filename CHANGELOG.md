# Changelog

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
