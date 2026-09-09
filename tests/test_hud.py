"""The HUD: what the watcher gets told. Content, not drawing."""

import random

from config import DEFAULT_CONFIG
from render.hud import equipment_lines, health_color, help_lines, hud_lines
from sim.tick import AgentState, tick
from world.tiles import Tile


class OpenWorld:
    """The smallest world a tick will accept."""

    def tile_at(self, x, y):
        return Tile.FLOOR if abs(x) < 40 and abs(y) < 40 else Tile.WALL

    def ensure_loaded(self, position):
        pass


def _running_agent(ticks: int = 3) -> AgentState:
    agent = AgentState(x=0, y=0)
    rng = random.Random(1)
    for _ in range(ticks):
        tick(agent, OpenWorld(), rng, DEFAULT_CONFIG)
    return agent


def _text(lines) -> str:
    return "\n".join(text for text, _ in lines)


def test_the_hud_reports_the_vitals():
    body = _text(hud_lines(_running_agent(), world_size=3, config=DEFAULT_CONFIG))
    assert "hp" in body
    assert "lvl" in body
    assert "goal" in body
    assert "build" in body
    assert "tick" in body


def test_the_hud_survives_an_agent_that_has_not_ticked_yet():
    """Drawn before the first tick, it must say something rather than explode."""
    lines = hud_lines(AgentState(x=0, y=0), world_size=0, config=DEFAULT_CONFIG)
    assert lines and isinstance(lines[0][0], str)


def test_the_hud_shows_the_numbers_the_agent_is_actually_using():
    """Sight and recall come from the effective config, not the config file."""
    agent = _running_agent()
    agent.derived = agent.derived.__class__(
        **{**agent.derived.__dict__, "fov_radius": 99, "memory_ttl": 12345}
    )
    body = _text(hud_lines(agent, 3, DEFAULT_CONFIG))
    assert "99" in body
    assert "12345" in body


def test_health_colour_tracks_how_bad_things_are():
    good = health_color(30, 30, DEFAULT_CONFIG)
    warn = health_color(15, 30, DEFAULT_CONFIG)
    bad = health_color(3, 30, DEFAULT_CONFIG)
    assert good == DEFAULT_CONFIG.hud_good_color
    assert warn == DEFAULT_CONFIG.hud_warn_color
    assert bad == DEFAULT_CONFIG.hud_bad_color
    assert len({good, warn, bad}) == 3


def test_health_colour_copes_with_a_zero_maximum():
    assert health_color(0, 0, DEFAULT_CONFIG) == DEFAULT_CONFIG.hud_bad_color


def test_the_goal_is_coloured_by_which_goal_it_is():
    agent = _running_agent()
    agent.goal_name = "FLEE"
    fleeing = dict(hud_lines(agent, 3, DEFAULT_CONFIG))
    agent.goal_name = "EXPLORE"
    exploring = dict(hud_lines(agent, 3, DEFAULT_CONFIG))
    assert fleeing["goal   FLEE"] == DEFAULT_CONFIG.hud_bad_color
    assert exploring["goal   EXPLORE"] == DEFAULT_CONFIG.hud_good_color


def test_paused_and_speed_are_visible():
    agent = _running_agent()
    assert "PAUSED" in _text(hud_lines(agent, 3, DEFAULT_CONFIG, speed=4, paused=True))
    assert "4x" in _text(hud_lines(agent, 3, DEFAULT_CONFIG, speed=4, paused=False))


def test_empty_slots_read_as_empty():
    body = _text(equipment_lines(_running_agent(), DEFAULT_CONFIG))
    assert "weapon" in body and "-" in body


def test_a_cursed_item_is_flagged_in_its_own_colour():
    from sim.affixes import BY_KEY
    from sim.items import ITEMS
    from world.populate import Item

    kinds = {k.key: k for k in ITEMS}
    agent = _running_agent()
    agent.equipped["weapon"] = Item(
        kind=kinds["weapon"], x=0, y=0, rarity="rare", affixes=(BY_KEY["dull"],)
    )
    colours = {text: color for text, color in equipment_lines(agent, DEFAULT_CONFIG)}
    cursed_line = next(t for t in colours if "weapon" in t and "dull" in t)
    assert colours[cursed_line] == DEFAULT_CONFIG.hud_bad_color


def test_the_key_map_mentions_the_keys_that_exist():
    body = _text(help_lines(DEFAULT_CONFIG))
    for key in ("space", "F1", "F5", "n ", "p "):
        assert key in body
