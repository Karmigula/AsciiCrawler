"""Sealed chambers, what is in them, and the stall down the corridor."""

from collections import deque

import numpy as np

from config import DEFAULT_CONFIG
from sim.session import Session
from world import secrets
from world.tiles import Tile


def _chambers(world, span=8):
    return [
        (cx, cy)
        for cx in range(-span, span + 1)
        for cy in range(-span, span + 1)
        if world.get_chunk(cx, cy).contents.secret is not None
    ]


def _walkable_from(tiles, start, goal):
    seen = {start}
    queue = deque([start])
    height, width = tiles.shape
    while queue:
        spot = queue.popleft()
        if spot == goal:
            return True
        x, y = spot
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            step = (x + dx, y + dy)
            if (
                0 <= step[0] < width
                and 0 <= step[1] < height
                and step not in seen
                and tiles[step[1], step[0]] != int(Tile.WALL)
            ):
                seen.add(step)
                queue.append(step)
    return False


def test_chambers_are_hidden_in_the_rock():
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    found = _chambers(session.world)

    assert found, "no chunk hid anything"
    for cx, cy in found[:6]:
        chunk = session.world.get_chunk(cx, cy)
        x, y, _kind = chunk.contents.secret
        size = DEFAULT_CONFIG.chunk_size
        lx, ly = x - cx * size, y - cy * size
        assert chunk.tiles[ly, lx] == int(Tile.FLOOR), "the room is not hollow"
        ring = chunk.tiles[ly - 2 : ly + 3, lx - 2 : lx + 3]
        assert np.all(ring[0] == int(Tile.WALL)), "it is open at the top"
        assert np.all(ring[-1] == int(Tile.WALL)), "it is open at the bottom"
        assert np.all(ring[:, 0] == int(Tile.WALL)), "it is open on the left"
        assert np.all(ring[:, -1] == int(Tile.WALL)), "it is open on the right"


def test_a_chamber_is_unreachable_until_the_door_is_opened():
    """The whole feature is this, so it is worth checking rather than assuming.

    An earlier `open_door` started its walk on the room's own floor, found
    open ground at once, cleared nothing, and reported success - so every
    chamber stayed sealed forever and the return value said otherwise.
    """
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    checked = opened = 0

    for cx, cy in _chambers(session.world)[:6]:
        chunk = session.world.get_chunk(cx, cy)
        x, y, _kind = chunk.contents.secret
        size = DEFAULT_CONFIG.chunk_size
        centre = (x - cx * size, y - cy * size)
        outside = next(
            (
                (px, py)
                for py in range(chunk.tiles.shape[0])
                for px in range(chunk.tiles.shape[1])
                if chunk.tiles[py, px] != int(Tile.WALL)
                and max(abs(px - centre[0]), abs(py - centre[1])) > 6
            ),
            None,
        )
        if outside is None:
            continue
        checked += 1
        assert not _walkable_from(chunk.tiles, outside, centre), "it was never sealed"
        assert session.world.open_secret(chunk)
        assert _walkable_from(chunk.tiles, outside, centre), "the door opened onto nothing"
        opened += 1

    assert opened >= 3, f"only {opened} chambers were checked properly"


def test_every_kind_of_room_is_one_the_game_knows_about():
    session = Session(DEFAULT_CONFIG, seed=5, record_hall=False)
    kinds = {
        session.world.get_chunk(cx, cy).contents.secret[2]
        for cx, cy in _chambers(session.world)
    }

    assert kinds, "no chambers at all"
    assert kinds <= set(secrets.LABELS), f"unknown kinds: {kinds - set(secrets.LABELS)}"


def test_the_same_world_hides_the_same_rooms():
    first = _chambers(Session(DEFAULT_CONFIG, seed=9, record_hall=False).world)
    again = _chambers(Session(DEFAULT_CONFIG, seed=9, record_hall=False).world)

    assert first and first == again


def test_a_chamber_is_noticed_by_standing_near_it():
    """A roll per tick while close, rather than a certainty at some range."""
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(10)
    chambers = _chambers(session.world, span=6)
    assert chambers, "nothing hidden nearby"
    chunk = session.world.get_chunk(*chambers[0])
    x, y, _kind = chunk.contents.secret

    for _ in range(600):
        session.agent.x, session.agent.y = x + 3, y
        session.advance(1)
        if session.agent.secrets_found:
            break

    assert session.agent.secrets_found == 1
    assert any("behind a wall" in text for _, text in session.agent.log.recent(10))


def test_a_still_pool_puts_the_creature_right():
    from sim.tick import _furnish_secret
    import random

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    session.agent.stats.hp = 3
    session.agent.stats.mp = 0

    _furnish_secret(
        session.agent,
        session.world,
        random.Random(1),
        DEFAULT_CONFIG,
        (session.agent.x, session.agent.y),
        "well",
    )

    assert session.agent.stats.hp == session.agent.derived.max_hp
    assert session.agent.stats.mp > 0


def test_a_gate_puts_it_somewhere_else_and_it_keeps_what_it_knows():
    """Memory survives the trip, which is the whole appeal of a gate."""
    import random

    from sim.tick import _furnish_secret

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(200)
    before = (session.agent.x, session.agent.y)
    knew = len(session.agent.memory)

    _furnish_secret(
        session.agent, session.world, random.Random(2), DEFAULT_CONFIG, before, "gate"
    )

    after = (session.agent.x, session.agent.y)
    gap = max(abs(after[0] - before[0]), abs(after[1] - before[1]))
    assert gap >= DEFAULT_CONFIG.secret_gate_distance // 2, f"it moved {gap} tiles"
    assert len(session.agent.memory) >= knew, "it forgot everything on the way"


def test_a_hoard_leaves_things_on_the_floor():
    import random

    from sim.tick import _furnish_secret

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    here = (session.agent.x, session.agent.y)
    before = sum(
        1
        for dx in range(-1, 2)
        for dy in range(-1, 2)
        if session.world.item_at(here[0] + dx, here[1] + dy) is not None
    )

    _furnish_secret(
        session.agent, session.world, random.Random(3), DEFAULT_CONFIG, here, "hoard"
    )

    after = sum(
        1
        for dx in range(-1, 2)
        for dy in range(-1, 2)
        if session.world.item_at(here[0] + dx, here[1] + dy) is not None
    )
    assert after > before, "the hoard was empty"


def test_a_baited_room_has_something_waiting_in_it():
    import random

    from sim.tick import _furnish_secret

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(5)
    here = (session.agent.x + 6, session.agent.y + 6)
    session.world.ensure_loaded(here)

    _furnish_secret(
        session.agent, session.world, random.Random(4), DEFAULT_CONFIG, here, "trap"
    )

    nearby = sum(
        1
        for dx in range(-2, 3)
        for dy in range(-2, 3)
        if session.world.entity_at(here[0] + dx, here[1] + dy) is not None
    )
    assert nearby > 0, "the trap was not baited"


def test_no_config_field_is_declared_twice():
    """A dataclass takes the last one, so a duplicate is a setting that lies.

    This happened: a half-applied patch left two copies of the secret-room
    block, and reading the first told you nothing about what the game used.
    """
    import re
    from collections import Counter

    source = open("config.py", encoding="utf-8").read()
    names = Counter(re.findall(r"^    ([a-z_]+):", source, re.M))
    repeated = {name: count for name, count in names.items() if count > 1}

    assert not repeated, f"declared more than once: {repeated}"
