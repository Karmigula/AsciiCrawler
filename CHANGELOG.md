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
- **Traps.** It spots them, remembers them, walks around them — and steps on
  one anyway when there is no other way past.

### Watching it

- **A title screen** with block-letter art. `esc` from the world goes back to
  it, and the creature keeps running while it is up, so *resume* resumes.
- **A resizable window**, `F10` for a borderless window and `F11` for
  borderless fullscreen. Both land on the monitor the window was already on,
  centred, rather than jumping to the primary one - the monitor layout is
  measured at startup, so stacked and offset arrangements work too. Borderless
  windows can still be resized. Making the window bigger shows more of the
  dungeon rather than magnifying it.
- **A HUD** with health, level, current goal, what it is wearing, and a rolling
  log of what just happened: *killed the rat*, *found a cruel sword*, *stepped
  in a trap*, *died in the dark*.
- **Five overlays** (`F1`–`F5`) that answer "why is it doing that?" by drawing
  what the agent *believes* rather than what is true: what it can see, how
  stale its memory is, where it thinks danger is, what it plans to walk, and
  where it still hopes to find something.
- **Pause and speed** — `space`, then `1`/`2`/`3` for 1x, 4x, 16x. 16x is the
  same simulation run faster, not a different one.
- **Screenshots** with `p`.
- **`run.bat`** — double-click and it starts.

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
- Long runs got slower and slower as the agent remembered more; roughly twice
  as fast now, and steady instead of degrading.
- Long item names ran off the edge of the screen. They wrap.
