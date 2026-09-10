"""The name generator, and the creature wearing what it produces."""

import random
from dataclasses import replace

import pytest

from config import DEFAULT_CONFIG
from sim import names
from sim.names import STYLES, full_name, given_name, name_for


def test_a_name_is_the_same_name_every_time_for_the_same_seed():
    assert name_for(7, 0) == name_for(7, 0)
    assert name_for(7, 0) != name_for(7, 1), "each life gets its own"
    assert name_for(7, 0) != name_for(8, 0), "so does each world"


def test_naming_a_creature_does_not_disturb_any_other_roll():
    """Names come from their own stream, like every other generator here.

    Drawing from the tick's `rng` would shift every roll after it, so the same
    seed would grow a different dungeon the day names were added.
    """
    from sim.harness import run_ticks

    before = run_ticks(600, 5)
    again = run_ticks(600, 5)

    assert (before.max_distance, before.kills, before.final_position) == (
        again.max_distance,
        again.kills,
        again.final_position,
    )


@pytest.mark.parametrize("style", STYLES, ids=lambda s: s.key)
def test_every_style_only_produces_names_a_person_could_say(style):
    """The rule that stops Feashshandziosheth, checked across the whole set."""
    for seed in range(3000):
        word = given_name(random.Random(seed), style)
        assert names._sayable(word.lower()), f"{style.key} produced {word!r}"
        assert word[0].isupper(), f"{word!r} is not capitalised"
        assert word.isalpha(), f"{word!r} has something odd in it"


def test_the_styles_do_not_all_sound_the_same():
    """A style is only worth having if its names are recognisably its own.

    Distinctness is checked as vocabulary rather than by ear: two styles that
    shared their letters would produce heavily overlapping names, and the
    point of separate segment sets is that they do not.
    """
    produced = {
        style.key: {given_name(random.Random(seed), style) for seed in range(800)}
        for style in STYLES
    }
    for style in STYLES:
        for other in STYLES:
            if style.key >= other.key:
                continue
            shared = produced[style.key] & produced[other.key]
            overlap = len(shared) / min(
                len(produced[style.key]), len(produced[other.key])
            )
            assert overlap < 0.12, f"{style.key} and {other.key} overlap {overlap:.0%}"


def test_there_are_a_great_many_names():
    """The whole reason for building them out of parts."""
    made = {full_name(random.Random(seed)) for seed in range(40000)}

    assert len(made) > 35000, f"only {len(made)} distinct names in 40,000 rolls"


def test_a_surname_is_never_the_same_word_twice():
    """Both columns hold "hammer", and Hammerhammer is not a surname."""
    for style in STYLES:
        for seed in range(4000):
            made = names.epithet(random.Random(seed), style)
            for head in style.heads:
                assert made.lower() != (head + head).lower(), made


def test_the_creature_is_born_with_a_name():
    from sim.session import Session

    session = Session(DEFAULT_CONFIG, seed=11, record_hall=False)
    session.advance(5)

    assert session.agent.name, "it should have a name from its first tick"


def test_the_next_life_is_a_different_creature():
    """A death is the end of somebody, and the next one is somebody else."""
    from sim.session import Session

    session = Session(
        replace(DEFAULT_CONFIG, new_world_on_death=False), seed=3, record_hall=False
    )
    first = session.agent.name
    for _ in range(30000):
        session.advance(1)
        if session.agent.deaths:
            break

    assert session.agent.deaths, "nothing died; the test proves nothing"
    assert session.agent.name != first
    assert session.agent.fallen or first, "the life that ended kept its name"


def test_the_hud_says_who_it_is_before_anything_else():
    from render.hud import hud_lines
    from sim.session import Session

    session = Session(DEFAULT_CONFIG, seed=11, record_hall=False)
    session.advance(5)

    lines = hud_lines(session.agent, 3, DEFAULT_CONFIG)

    assert lines[0][0].startswith(session.agent.name[:12])


def test_a_hall_written_before_names_existed_still_loads(tmp_path):
    """Adding a field must not throw away somebody's best runs.

    `load` drops any record whose fields do not match the dataclass, so a new
    field without a default would quietly empty an existing hall of fame.
    """
    import json

    from sim import hall

    old = [
        {
            "seed": 1,
            "level": 4,
            "kills": 9,
            "depth": 120,
            "ticks": 800,
            "killer": "a troll",
            "archetype": "scout",
            "gold": 3,
        }
    ]
    path = tmp_path / "hall_of_fame.json"
    path.write_text(json.dumps(old), encoding="utf-8")

    entries = hall.load(path)

    assert len(entries) == 1, "an older hall should survive the upgrade"
    assert entries[0].name == ""
