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
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from dataclasses import replace

from config import DEFAULT_CONFIG
from render.hud import chronicle_lines, equipment_lines, hud_lines
from sim.session import Session
from web.frame import serialize

STATIC = Path(__file__).parent / "static"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Everyone shares one frame, so the window cannot be tailored to each browser
# and its shape is a compromise. A character cell is about 1.6 times taller
# than it is wide, so 104x36 draws at roughly 16:9 and fills a maximised
# window instead of leaving bands down both sides.
#
# A frame is a few tens of milliseconds of Python, so a small instance will
# not always hit the target rate - and that is fine: falling behind makes the
# tank run slower, not wrong. Every knob is an environment variable, so a host
# that struggles can be dialled down without a deploy.
COLS = _env_int("CRAWLER_COLS", 104)
ROWS = _env_int("CRAWLER_ROWS", 36)
FPS = _env_int("CRAWLER_FPS", 8)
TICKS_PER_FRAME = _env_int("CRAWLER_TICKS_PER_FRAME", 1)
# Chunks are never discarded, so a world that runs for a month is a slow leak.
# Rotating also keeps the tank worth watching.
WORLD_TICKS = _env_int("CRAWLER_WORLD_TICKS", 40_000)
HUD_CHARS = _env_int("CRAWLER_HUD_CHARS", 46)


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
        """Send one prepared frame to everyone; drop whoever has gone away."""
        async with self._lock:
            watching = list(self._sockets)
        for socket in watching:
            try:
                await socket.send_text(payload)
            except Exception:
                await self.remove(socket)


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
    """Tick and broadcast while anyone is watching; idle otherwise."""
    session: Session = app.state.session
    viewers: Viewers = app.state.viewers
    interval = 1.0 / max(1, FPS)
    while True:
        await viewers.awake.wait()
        started = asyncio.get_running_loop().time()
        # The tick is ordinary blocking Python. It is short, and moving it to
        # a thread would buy nothing while the GIL is held anyway, so it runs
        # here and the sleep below absorbs the jitter.
        session.advance(TICKS_PER_FRAME)
        payload = build_payload(session, len(viewers))
        app.state.latest = payload
        await viewers.broadcast(payload)
        elapsed = asyncio.get_running_loop().time() - started
        await asyncio.sleep(max(0.0, interval - elapsed))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.session = Session(
        DEFAULT_CONFIG,
        seed=_env_int("CRAWLER_SEED", DEFAULT_CONFIG.world_seed),
        max_ticks=WORLD_TICKS,
        # A free host's disk is wiped on every deploy, so a hall of fame kept
        # there is a file that quietly lies about being permanent.
        record_hall=os.environ.get("CRAWLER_HALL", "0") == "1",
    )
    app.state.viewers = Viewers()
    app.state.latest = build_payload(app.state.session, 0)
    runner = asyncio.create_task(_run(app))
    try:
        yield
    finally:
        runner.cancel()


app = FastAPI(title="AsciiCrawler", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
async def healthz() -> JSONResponse:
    """Enough for a host's health check, and for me to see it is alive."""
    session: Session = app.state.session
    return JSONResponse(
        {
            "ok": True,
            "tick": session.agent.tick_count,
            "seed": session.seed,
            "worlds": session.worlds,
            "viewers": len(app.state.viewers),
        }
    )


@app.get("/api/frame")
async def frame() -> JSONResponse:
    """The last frame, as JSON. Handy without a socket, and for debugging."""
    return JSONResponse(json.loads(app.state.latest))


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
