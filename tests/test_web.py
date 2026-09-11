"""The web layer: the frame it sends, and the session behind it.

The server itself is thin on purpose. What is worth pinning is that the thing
it serializes is the same picture the desktop draws, that a long-running host
does not leak, and that nothing in the serving path drags pygame in.
"""

import json
import subprocess
import sys
from dataclasses import replace

import pytest

from config import DEFAULT_CONFIG
from sim.session import Session, should_restart
from web.frame import serialize


def _session(seed=3, **kwargs):
    return Session(DEFAULT_CONFIG, seed=seed, record_hall=False, **kwargs)


def test_a_frame_covers_the_whole_window():
    session = _session()
    session.advance(120)

    frame = serialize(session.world, session.agent, session.config, 40, 20)

    assert (frame["cols"], frame["rows"]) == (40, 20)
    assert len(frame["glyphs"]) == 20
    assert all(len(row) == 40 for row in frame["glyphs"])
    assert len(frame["fg"]) == 20 and len(frame["bg"]) == 20


def test_a_frame_survives_a_round_trip_through_json():
    """Everything in it has to be a plain type; a Colour tuple is not one."""
    session = _session()
    session.advance(60)

    frame = serialize(session.world, session.agent, session.config, 30, 16)
    again = json.loads(json.dumps(frame))

    assert again["glyphs"] == frame["glyphs"]
    assert again["palette"] == frame["palette"]


def test_run_length_colours_expand_back_to_one_per_cell():
    """The client trusts the runs to cover the row; this is that promise."""
    session = _session()
    session.advance(80)
    cols = 36

    frame = serialize(session.world, session.agent, session.config, cols, 18)

    for runs in frame["fg"] + frame["bg"]:
        assert sum(runs[1::2]) == cols, f"runs cover {sum(runs[1::2])} of {cols}"
        assert all(index < len(frame["palette"]) for index in runs[0::2])


def test_the_agent_is_drawn_at_the_middle_of_its_own_window():
    """Nobody is steering, so the camera has nowhere to be but on the agent."""
    session = _session()
    session.advance(200)

    frame = serialize(session.world, session.agent, session.config, 41, 21)

    assert frame["agent"][:2] == [20, 10]


def test_the_frame_names_the_biome_the_agent_is_standing_in():
    session = _session()
    session.advance(50)

    frame = serialize(session.world, session.agent, session.config, 20, 10)

    assert frame["biome"] == session.world.biome_at(
        session.agent.x, session.agent.y
    ).label


def test_a_session_rotates_its_world_before_it_grows_without_bound():
    """Chunks are never discarded, so a server that never rotates leaks.

    A month of uptime is the case the desktop app never had to survive.
    """
    session = _session(max_ticks=40)
    first_seed = session.seed

    session.advance(45)

    assert session.seed != first_seed, "the world should have rolled over"
    assert session.worlds == 2
    assert session.agent.tick_count < 40, "and the new one starts fresh"


def test_a_rotated_world_is_a_real_new_world():
    session = _session(max_ticks=30)
    before = len(session.world)

    session.advance(35)
    session.advance(30)

    assert session.worlds >= 2
    assert len(session.world) <= before + 40, "chunks should not accumulate forever"


def test_death_rolls_a_new_world_when_that_is_how_it_is_set_up():
    staying = replace(DEFAULT_CONFIG, new_world_on_death=False)
    leaving = replace(DEFAULT_CONFIG, new_world_on_death=True)

    assert should_restart(leaving, 1, 0) is True
    assert should_restart(staying, 1, 0) is False


def test_serving_a_frame_does_not_need_pygame():
    """A headless host should not be installing SDL to draw nothing.

    `render/` is allowed to be imported here - it is the frame builder - but
    the pygame part of it lives in `render/screen.py` and must stay out.
    """
    code = (
        "import sys;"
        "import web.frame, sim.session;"
        "assert 'pygame' not in sys.modules, sorted(m for m in sys.modules if 'pygame' in m);"
        "print('clean')"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert done.returncode == 0, done.stderr
    assert "clean" in done.stdout


def test_the_app_imports_and_exposes_its_routes():
    pytest.importorskip("fastapi")
    from web.app import app

    paths = {route.path for route in app.routes}
    assert {"/", "/healthz", "/api/frame", "/ws"} <= paths


def test_the_frame_says_what_the_agent_is_wearing():
    """The desktop HUD has always shown this; the browser was missing it."""
    from render.hud import equipment_lines

    session = _session()
    session.advance(400)

    frame = serialize(
        session.world,
        session.agent,
        session.config,
        20,
        10,
        worn=equipment_lines(session.agent, session.config),
    )

    slots = " ".join(text for text, _ in frame["worn"])
    assert "worn" in slots
    for slot in ("weapon", "armor", "ring", "amulet"):
        assert slot in slots, f"{slot} is missing from the worn panel"


def test_the_worn_panel_is_optional():
    """A caller that does not pass one should get an empty list, not a crash."""
    session = _session()
    session.advance(20)

    frame = serialize(session.world, session.agent, session.config, 20, 10)

    assert frame["worn"] == []


def test_a_bad_frame_costs_a_frame_and_not_the_aquarium():
    """One loop feeds every viewer, so an exception in it froze everybody.

    The task would end, nothing would restart it, and the page would sit on
    its last frame with the socket still open and the health check still
    saying yes. A frame that fails should cost a frame.
    """
    import asyncio
    from types import SimpleNamespace

    pytest.importorskip("fastapi")
    import web.app as web_app

    class FakeSocket:
        def __init__(self):
            self.sent = []

        async def send_text(self, payload):
            self.sent.append(payload)

    async def scenario():
        state = SimpleNamespace(
            session=_session(),
            viewers=web_app.Viewers(),
            latest="",
            failures=0,
            failing=0,
            frames=0,
        )
        app = SimpleNamespace(state=state)
        socket = FakeSocket()
        await state.viewers.add(socket)

        calls = {"n": 0}
        real = web_app.build_payload

        def sometimes_broken(session, viewers):
            calls["n"] += 1
            if calls["n"] <= 3:
                raise RuntimeError("a frame went wrong")
            return real(session, viewers)

        web_app.build_payload = sometimes_broken
        runner = asyncio.create_task(web_app._run(app))
        try:
            for _ in range(120):
                await asyncio.sleep(0.05)
                if state.frames >= 2:
                    break
        finally:
            runner.cancel()
            web_app.build_payload = real
            try:
                await runner
            except asyncio.CancelledError:
                pass
        return state, socket, runner

    state, socket, runner = asyncio.run(scenario())

    assert state.failures == 3, f"failures were not counted: {state.failures}"
    assert state.frames >= 2, "the loop did not recover and keep drawing"
    assert socket.sent, "viewers got nothing after the failure"


def test_the_health_check_fails_when_the_loop_behind_it_has_stopped():
    """A host that restarts on a failed check should get the chance to.

    Answering yes because the web server is up would miss the failure that
    actually matters - the loop behind it having stopped - and the page would
    sit frozen while everything reported healthy.
    """
    import asyncio

    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")  # what TestClient drives the app through
    from fastapi.testclient import TestClient

    from web.app import app

    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200, "should start healthy"

        # A finished stand-in for the runner. Cancelling the real task from
        # here would mean reaching into the test client's event loop from
        # another one; `done()` is all the endpoint asks about.
        spare = asyncio.new_event_loop()
        try:
            finished = spare.create_future()
            finished.set_result(None)
            running, app.state.runner = app.state.runner, finished
            try:
                answer = client.get("/healthz")
            finally:
                app.state.runner = running
        finally:
            spare.close()

    assert answer.status_code == 503
    assert answer.json()["ok"] is False


def test_one_stuck_viewer_does_not_hold_up_everybody_else():
    """Sends are concurrent and deadlined, because a send does not fail fast.

    A client that stops reading - a backgrounded tab, a sleeping phone - keeps
    the send waiting for the transport to drain, which is minutes. Sent one
    after another, that stalled the tick loop and froze the shared world for
    every other viewer.
    """
    import asyncio
    import time

    pytest.importorskip("fastapi")
    import web.app as web_app

    class Stuck:
        async def send_text(self, payload):
            await asyncio.sleep(30)  # never lands

    class Fine:
        def __init__(self):
            self.sent = []

        async def send_text(self, payload):
            self.sent.append(payload)

    async def scenario():
        viewers = web_app.Viewers()
        stuck, fine = Stuck(), Fine()
        await viewers.add(stuck)
        await viewers.add(fine)
        started = time.perf_counter()
        await viewers.broadcast("frame")
        return time.perf_counter() - started, fine, len(viewers)

    took, fine, left = asyncio.run(scenario())

    assert fine.sent == ["frame"], "the healthy viewer should have been served"
    assert took < web_app.SEND_TIMEOUT + 1.0, f"broadcast took {took:.1f}s"
    assert left == 1, "the stuck viewer should have been dropped"


def test_the_backoff_grows_with_consecutive_failures_not_lifetime_ones():
    """A hiccup months later should cost a quarter second, not five.

    The counter that /healthz reports is a lifetime total, so using it for the
    backoff meant a long-lived instance paused for the ceiling on its next
    single failure.
    """
    import asyncio
    from types import SimpleNamespace

    pytest.importorskip("fastapi")
    import web.app as web_app

    class FakeSocket:
        async def send_text(self, payload):
            pass

    async def scenario():
        state = SimpleNamespace(
            session=_session(), viewers=web_app.Viewers(),
            latest="", failures=0, failing=0, frames=0,
        )
        app = SimpleNamespace(state=state)
        await state.viewers.add(FakeSocket())
        calls = {"n": 0}
        real = web_app.build_payload

        def flaky(session, viewers):
            calls["n"] += 1
            if calls["n"] in (1, 2):
                raise RuntimeError("hiccup")
            return real(session, viewers)

        web_app.build_payload = flaky
        runner = asyncio.create_task(web_app._run(app))
        try:
            for _ in range(120):
                await asyncio.sleep(0.05)
                if state.frames >= 2:
                    break
        finally:
            runner.cancel()
            web_app.build_payload = real
            try:
                await runner
            except asyncio.CancelledError:
                pass
        return state

    state = asyncio.run(scenario())

    assert state.failures == 2, "the lifetime count is what /healthz reports"
    assert state.failing == 0, "a good frame ends the run of bad ones"


def test_each_boot_opens_on_a_different_world():
    """A fixed starting seed replayed the same dungeons on every restart.

    On a host that sleeps between visitors that is not a quirk, it is the main
    thing anybody sees: the instance wakes, starts where it always starts, and
    a returning viewer meets the same creature by name again and again.
    """
    import os

    pytest.importorskip("fastapi")
    from web.app import starting_seed

    was = os.environ.pop("CRAWLER_SEED", None)
    try:
        seeds = {starting_seed() for _ in range(20)}
    finally:
        if was is not None:
            os.environ["CRAWLER_SEED"] = was

    assert len(seeds) > 15, f"boots are not rolling their own world: {seeds}"


def test_a_world_can_still_be_asked_for_by_name():
    """Reproducing one is worth keeping; that is the whole point of seeds."""
    import os

    pytest.importorskip("fastapi")
    from web.app import starting_seed

    was = os.environ.get("CRAWLER_SEED")
    os.environ["CRAWLER_SEED"] = "4242"
    try:
        assert [starting_seed() for _ in range(3)] == [4242, 4242, 4242]
    finally:
        if was is None:
            os.environ.pop("CRAWLER_SEED", None)
        else:
            os.environ["CRAWLER_SEED"] = was


def test_a_nonsense_seed_rolls_one_rather_than_refusing_to_start():
    import os

    pytest.importorskip("fastapi")
    from web.app import starting_seed

    was = os.environ.get("CRAWLER_SEED")
    os.environ["CRAWLER_SEED"] = "the frozen deep"
    try:
        assert starting_seed() != starting_seed()
    finally:
        if was is None:
            os.environ.pop("CRAWLER_SEED", None)
        else:
            os.environ["CRAWLER_SEED"] = was


def test_every_death_moves_to_a_world_this_session_has_not_seen():
    """A death should open somewhere new, not next door.

    Worlds used to be seed + 1, so a run was a walk through neighbouring
    dungeons; combined with a fixed start that meant the same short procession
    of them, and the same creatures by name, on every restart.
    """
    session = _session(seed=4242, max_ticks=25)
    seeds = [session.seed]
    for _ in range(40):
        session._next_world()
        seeds.append(session.seed)

    assert len(set(seeds)) == len(seeds), "a world came round twice"
    assert all(abs(b - a) > 1 for a, b in zip(seeds, seeds[1:])), (
        "worlds are still neighbours"
    )


def test_a_pinned_seed_reproduces_the_whole_procession():
    """Randomness per death must not cost reproducibility.

    The worlds after the first are drawn from a stream seeded by the first, so
    naming one world names all of them - which is what makes a report like
    "the third world on seed 4242" mean anything.
    """
    def walk():
        session = _session(seed=4242)
        seen = [session.seed]
        for _ in range(6):
            session._next_world()
            seen.append(session.seed)
        return seen

    assert walk() == walk()


def test_different_starting_worlds_lead_somewhere_different():
    def walk(seed):
        session = _session(seed=seed)
        seen = []
        for _ in range(6):
            session._next_world()
            seen.append(session.seed)
        return set(seen)

    assert not (walk(11) & walk(12)), "two boots visited the same worlds"


def test_the_hall_can_be_kept_somewhere_that_survives_a_deploy(tmp_path):
    """A host with a real disk should be able to keep the scoreboard.

    It is off by default because a filesystem rebuilt on every deploy makes a
    hall of fame a file that quietly lies about being permanent - but given a
    path that lasts, these are the only lives that outlive their world.
    """
    from dataclasses import replace

    from config import DEFAULT_CONFIG
    from sim import hall
    from sim.session import Session

    where = tmp_path / "hall_of_fame.json"
    session = Session(
        replace(DEFAULT_CONFIG, new_world_on_death=False),
        seed=3,
        record_hall=True,
        hall_path=where,
    )
    for _ in range(30000):
        session.advance(1)
        if session.agent.deaths:
            break

    assert session.agent.deaths, "nothing died; the test proves nothing"
    assert where.exists(), "the hall was not written where it was asked for"
    entries = hall.load(where)
    assert entries and entries[0].name, "the life that ended was not recorded"


def test_the_server_entry_point_starts_the_web_app_not_the_desktop_game():
    """`main.py` opens a pygame window, and hosts guess that name.

    A platform that picks an entry point by filename would find the desktop
    game and try to open a window on a machine with no screen, so there is a
    `server.py` for it to find instead.
    """
    import ast

    source = open("server.py", encoding="utf-8").read()
    tree = ast.parse(source)
    targets = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "web.app:app" in targets, "server.py does not start the web app"
    assert "PORT" in targets, "server.py ignores the host's port"


def test_the_hall_is_served_for_the_overlay_to_show():
    """Visitors cannot open a settings screen, so the hall comes over HTTP."""
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from web.app import app

    with TestClient(app) as client:
        answer = client.get("/api/hall")

    assert answer.status_code == 200
    body = answer.json()
    assert "lives" in body and isinstance(body["lives"], list)
    assert "kept" in body, "the page needs to know whether these lives persist"
    for life in body["lives"]:
        assert {"name", "level", "kills", "depth", "score"} <= set(life)
