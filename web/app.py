"""The aquarium, on a socket.

One world ticks here and everyone watches the same one. That is not a
shortcut - it is what the game is. Nobody plays AsciiCrawler, so there is no
input to keep separate per visitor, and a public tank costs the same to run
whether one person is looking or fifty: the simulation runs once and the same
bytes go to every socket.

It ticks only while somebody is connected. An empty room costs nothing, which
is what makes this fit on a free instance.
"""

import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dataclasses import replace

from config import DEFAULT_CONFIG
from render.hud import chronicle_lines, equipment_lines, hud_lines
from sim import hall
from sim.session import Session
from web.frame import serialize

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("asciicrawler")

# How long to wait after a frame fails, growing with consecutive failures
# so a permanently broken world does not spin a core rendering nothing.
RETRY_CEILING = 5.0

# How long one viewer gets to accept a frame. A send does not fail when a
# client stops reading - it waits for the transport to drain, which for a
# suspended tab or a sleeping phone means minutes. Sequential sends made that
# everybody's problem: the loop could not tick again until the slowest socket
# finished, so one dead connection froze the shared world.
SEND_TIMEOUT = 2.0


def starting_seed() -> int:
    """Which world to open on: the one asked for, or one nobody has seen.

    A fixed default made every boot replay the same dungeons in the same
    order, which on a host that sleeps between visitors is not a quirk but the
    main thing you see. The instance wakes, starts at 4242, and the third
    creature it names is the one a returning viewer keeps meeting - the same
    name, over and over, in a game with fifty thousand of them.

    `CRAWLER_SEED` still pins it, because reproducing a world is worth
    keeping. Without it the seed is random per boot and logged, so a world
    that turns out to be worth watching can be asked for again.
    """
    asked = os.environ.get("CRAWLER_SEED")
    if asked is not None:
        try:
            return int(asked)
        except ValueError:
            log.warning("CRAWLER_SEED=%r is not a number; rolling one", asked)
    return secrets.randbelow(1 << 31)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Everyone shares one frame, so the window cannot be tailored to each browser
# and its shape is a compromise. A character cell is about 1.6 times taller
# than it is wide, so 120x44 draws at roughly 16:9 and fills a maximised
# window instead of leaving bands down both sides.
#
# A frame that size measures about 25ms to build, so twelve a second is
# roughly a third of one core. The earlier 104x36 at eight was sized for a
# free tier metered at a tenth of a core; this is sized for a box that has
# one to spend.
#
# A frame is a few tens of milliseconds of Python, so a small instance will
# not always hit the target rate - and that is fine: falling behind makes the
# tank run slower, not wrong. Every knob is an environment variable, so a host
# that struggles can be dialled down without a deploy.
COLS = _env_int("CRAWLER_COLS", 120)
ROWS = _env_int("CRAWLER_ROWS", 44)
FPS = _env_int("CRAWLER_FPS", 12)
TICKS_PER_FRAME = _env_int("CRAWLER_TICKS_PER_FRAME", 1)
# Chunks are never discarded, so a world that runs for a month is a slow leak.
# Rotating also keeps the tank worth watching.
WORLD_TICKS = _env_int("CRAWLER_WORLD_TICKS", 40_000)
HUD_CHARS = _env_int("CRAWLER_HUD_CHARS", 46)
# Where to keep the hall of fame. Off unless asked for, because a host that
# rebuilds its filesystem on every deploy turns a scoreboard into a file that
# quietly lies about being permanent. Given a path on a real disk, it is worth
# having: these are the only lives that outlast their world.
HALL_PATH = os.environ.get("CRAWLER_HALL_PATH")
# The desktop defaults to staying in the same dungeon after a death, so the
# next life can walk back for its own gear. Watching a stream, a death is the
# end of a story and the interesting thing is a new one somewhere else - so
# the hosted version rolls a fresh world instead.
NEW_WORLD_ON_DEATH = os.environ.get("CRAWLER_NEW_WORLD_ON_DEATH", "1") == "1"


class Viewers:
    """Everyone currently watching, and the loop that feeds them."""

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.awake = asyncio.Event()

    def __len__(self) -> int:
        return len(self._sockets)

    async def add(self, socket: WebSocket) -> None:
        async with self._lock:
            self._sockets.add(socket)
        self.awake.set()

    async def remove(self, socket: WebSocket) -> None:
        async with self._lock:
            self._sockets.discard(socket)
        if not self._sockets:
            self.awake.clear()

    async def broadcast(self, payload: str) -> None:
        """Send one prepared frame to everyone at once; drop whoever cannot take it.

        Concurrent rather than one after another, and each send is given a
        deadline. A viewer who has stopped reading - a backgrounded tab, a
        phone that went to sleep - otherwise holds the whole tank still until
        TCP gives up on them, which is minutes. Missing a frame is the right
        cost for that; everyone else should not miss it too.
        """
        async with self._lock:
            watching = list(self._sockets)
        if not watching:
            return
        results = await asyncio.gather(
            *(self._send(socket, payload) for socket in watching),
            return_exceptions=True,
        )
        for socket, failed in zip(watching, results):
            if failed is not None:
                await self.remove(socket)

    async def _send(self, socket: WebSocket, payload: str):
        """Hand one viewer a frame; return the reason if it did not land."""
        try:
            await asyncio.wait_for(socket.send_text(payload), timeout=SEND_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception as reason:
            return reason
        return None


def build_payload(session: Session, viewers: int) -> str:
    """Serialize the current frame once, for every viewer to share."""
    config = session.config
    agent = session.agent
    here = session.world.biome_at(agent.x, agent.y)
    # The desktop clips HUD lines to the width of its side panel. A browser
    # panel is wider, and "found a amulet of the lo..." helps nobody.
    wide = replace(config, hud_max_chars=HUD_CHARS)
    frame = serialize(
        session.world,
        agent,
        config,
        COLS,
        ROWS,
        hud=hud_lines(agent, len(session.world), wide, biome=(here.key, here.label)),
        worn=equipment_lines(agent, wide),
        log=chronicle_lines(agent, wide),
        viewers=viewers,
    )
    frame["seed"] = session.seed
    frame["worlds"] = session.worlds
    return json.dumps(frame, separators=(",", ":"))


async def _run(app: FastAPI) -> None:
    """Tick and broadcast while anyone is watching; idle otherwise.

    One loop feeds every viewer, which is the point and also the risk: if it
    ever raises, the task ends, and nothing restarts it. The aquarium would
    then sit frozen on its last frame for everybody, with the sockets still
    open and the health check still cheerfully saying yes.

    So a bad frame costs a frame. The failure is logged, counted, and backed
    off - a world that is broken rather than unlucky should not spin a core
    failing sixty times a second - and the loop carries on. Cancellation is
    the one thing that gets through, because that is the shutdown path.
    """
    session: Session = app.state.session
    viewers: Viewers = app.state.viewers
    interval = 1.0 / max(1, FPS)
    while True:
        await viewers.awake.wait()
        started = asyncio.get_running_loop().time()
        try:
            # The tick is ordinary blocking Python. It is short, and moving it
            # to a thread would buy nothing while the GIL is held anyway, so it
            # runs here and the sleep below absorbs the jitter.
            session.advance(TICKS_PER_FRAME)
            payload = build_payload(session, len(viewers))
        except asyncio.CancelledError:
            raise
        except Exception:
            app.state.failures += 1
            app.state.failing += 1
            log.exception("frame %s failed", session.agent.tick_count)
            await asyncio.sleep(min(RETRY_CEILING, 0.25 * app.state.failing))
            continue
        # A frame that worked ends the run of bad ones. Backing off on the
        # lifetime count instead would make a single hiccup, months later,
        # cost the full five seconds.
        app.state.failing = 0
        app.state.latest = payload
        app.state.frames += 1
        await viewers.broadcast(payload)
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0.0, interval - elapsed))


def _speak_through_uvicorn() -> None:
    """Borrow the server's log handlers, so our own lines are not swallowed.

    Uvicorn configures its loggers and leaves the root one bare, so a plain
    `getLogger(...)` writes into nothing. The starting seed is the one thing
    here worth being able to find afterwards - it is how a world that turned
    out to be worth watching gets asked for again - and it was going
    precisely nowhere.
    """
    if log.handlers:
        return
    # The handler is not on "uvicorn.error" - that one propagates, and the
    # handler sits on its parent - so walk up until something can actually
    # write. Checking only the first name is how this silently did nothing.
    for name in ("uvicorn.error", "uvicorn", "root"):
        server = logging.getLogger() if name == "root" else logging.getLogger(name)
        if server.handlers:
            log.handlers = server.handlers
            log.setLevel(logging.INFO)
            return


@asynccontextmanager
async def lifespan(app: FastAPI):
    _speak_through_uvicorn()
    seed = starting_seed()
    log.info("opening on world seed %s", seed)
    app.state.session = Session(
        replace(DEFAULT_CONFIG, new_world_on_death=NEW_WORLD_ON_DEATH),
        seed=seed,
        max_ticks=WORLD_TICKS,
        record_hall=bool(HALL_PATH) or os.environ.get("CRAWLER_HALL", "0") == "1",
        hall_path=Path(HALL_PATH) if HALL_PATH else None,
    )
    app.state.viewers = Viewers()
    app.state.failures = 0  # lifetime, reported by /healthz
    app.state.failing = 0  # consecutive, what the backoff grows with
    app.state.frames = 0
    # One tick before the first frame is built: the HUD reads "booting" until
    # the creature has stats, and a visitor waking a sleeping instance should
    # not be shown that.
    app.state.session.advance(1)
    app.state.latest = build_payload(app.state.session, 0)
    app.state.runner = asyncio.create_task(_run(app))
    try:
        yield
    finally:
        app.state.runner.cancel()


app = FastAPI(title="AsciiCrawler", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """Whether the thing is alive, in the sense a host should care about.

    Answering yes because the web server is up would miss the failure that
    actually matters: the loop behind it having stopped. If the runner is
    done, the page is a frozen picture, and a host that restarts on a failed
    health check should get the chance to.
    """
    session: Session = app.state.session
    runner = app.state.runner
    alive = not runner.done()
    return JSONResponse(
        {
            "ok": alive,
            "tick": session.agent.tick_count,
            "seed": session.seed,
            "worlds": session.worlds,
            "viewers": len(app.state.viewers),
            "frames": app.state.frames,
            "failures": app.state.failures,
        },
        status_code=200 if alive else 503,
    )


@app.get("/api/frame")
async def frame() -> JSONResponse:
    """The last frame, as JSON. Handy without a socket, and for debugging."""
    return JSONResponse(json.loads(app.state.latest))


@app.get("/api/hall")
async def hall_of_fame() -> JSONResponse:
    """The best lives this instance remembers, for the overlay to show.

    Fetched when somebody opens it rather than carried on every frame: it
    changes when something dies, which is rarely, and a frame goes out a
    dozen times a second to everyone at once.
    """
    entries = hall.load(Path(HALL_PATH) if HALL_PATH else None)
    return JSONResponse(
        {
            "kept": bool(HALL_PATH) or os.environ.get("CRAWLER_HALL") == "1",
            "lives": [
                {
                    "name": entry.name or "someone",
                    "level": entry.level,
                    "kills": entry.kills,
                    "depth": entry.depth,
                    "ticks": entry.ticks,
                    "killer": entry.killer,
                    "build": entry.archetype,
                    "score": hall.score(entry),
                }
                for entry in entries
            ],
        }
    )


@app.websocket("/ws")
async def stream(socket: WebSocket) -> None:
    await socket.accept()
    viewers: Viewers = app.state.viewers
    await viewers.add(socket)
    try:
        await socket.send_text(app.state.latest)  # something to look at at once
        while True:
            # Nothing is expected from the client; this waits for the socket
            # to close and keeps the connection honest.
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        await viewers.remove(socket)
