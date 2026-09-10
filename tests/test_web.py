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
