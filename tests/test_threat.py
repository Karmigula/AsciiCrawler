"""Fear: the threat field, and the FLEE goal that overrides exploration."""

import random
from dataclasses import replace

from agent.goals import ExploreGoal, FleeGoal
from agent.memory import Memory
from agent.stats import Stats
from agent.threat import danger, flee_threshold, remembered_monsters
from config import DEFAULT_CONFIG
from world.tiles import Tile


def _corridor(length: int = 30, entities=None) -> Memory:
    memory = Memory()
    memory.observe(
        {(x, y): Tile.FLOOR for x in range(length) for y in range(3)},
        tick=1,
        entities=entities or {},
    )
    return memory


def test_threat_falls_off_with_distance():
    memory = _corridor(entities={(10, 1): "T"})
    close = danger(memory, (9, 1), DEFAULT_CONFIG)
    far = danger(memory, (16, 1), DEFAULT_CONFIG)
    assert close > far > 0


def test_a_dragon_frightens_more_than_a_rat():
    dragon = danger(_corridor(entities={(5, 1): "D"}), (4, 1), DEFAULT_CONFIG)
    rat = danger(_corridor(entities={(5, 1): "r"}), (4, 1), DEFAULT_CONFIG)
    assert dragon > rat


def test_monsters_beyond_the_threat_radius_are_ignored():
    beyond = DEFAULT_CONFIG.threat_radius + 3
    memory = _corridor(length=beyond + 5, entities={(beyond, 1): "D"})
    assert danger(memory, (0, 1), DEFAULT_CONFIG) == 0.0


def test_threat_is_read_off_memory_not_off_the_world():
    """The agent fears the troll it saw, where it last saw it — it will flee a
    monster that has already wandered away. That is the belief rule, not a bug."""
    memory = _corridor(entities={(6, 1): "T"})
    assert danger(memory, (5, 1), DEFAULT_CONFIG) > 0
    memory.observe({(6, 1): Tile.FLOOR}, tick=2)  # looked again: it had gone
    assert danger(memory, (5, 1), DEFAULT_CONFIG) == 0.0


def test_only_monster_glyphs_count_as_threatening():
    memory = _corridor()
    memory.observe({(5, 1): Tile.FLOOR}, tick=2, items={(5, 1): "!"})
    assert danger(memory, (4, 1), DEFAULT_CONFIG) == 0.0
    assert remembered_monsters(memory, (4, 1), 5) == []


def test_a_hurt_agent_runs_from_less():
    stats = Stats.starting(DEFAULT_CONFIG)
    full = flee_threshold(stats, DEFAULT_CONFIG)
    stats.hp = stats.max_hp // 3
    assert flee_threshold(stats, DEFAULT_CONFIG) < full


def test_flee_takes_control_when_danger_passes_the_threshold():
    goal = FleeGoal()
    stats = Stats.starting(DEFAULT_CONFIG)
    calm = _corridor()
    assert not goal.wants_control((5, 1), calm, stats, DEFAULT_CONFIG)
    scary = _corridor(entities={(6, 1): "D"})
    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG)


def test_flight_releases_on_hysteresis_not_on_the_trigger():
    """Otherwise the agent stutters in and out of flight on the boundary."""
    config = replace(DEFAULT_CONFIG, flee_threat=1.0, flee_release=0.5)
    goal = FleeGoal()
    stats = Stats.starting(config)
    memory = _corridor(entities={(6, 1): "o"})  # threat 2.0 at range 2 -> 0.67
    goal.active = True
    borderline = danger(memory, (4, 1), config)
    assert 0.5 < borderline < 1.0  # under the trigger, over the release
    assert goal.wants_control((4, 1), memory, stats, config)
    goal.active = False
    assert not goal.wants_control((4, 1), memory, stats, config)


def test_fleeing_walks_toward_calmer_ground():
    memory = _corridor(entities={(2, 1): "D"})
    goal = FleeGoal()
    path = goal.decide((5, 1), memory, DEFAULT_CONFIG)
    assert path, "the agent should have somewhere to run"
    assert path[-1][0] > 5  # away from the dragon, not past it
    assert danger(memory, path[-1], DEFAULT_CONFIG) < danger(
        memory, (5, 1), DEFAULT_CONFIG
    )


def test_standing_down_hands_control_back():
    goal = FleeGoal()
    goal.decide((5, 1), _corridor(entities={(2, 1): "D"}), DEFAULT_CONFIG)
    assert goal.active
    goal.stand_down()
    assert not goal.active and goal.path == []


def test_threat_discounts_an_explore_candidate():
    """Even when not frightened enough to run, the agent prefers calm frontier."""
    config = replace(DEFAULT_CONFIG, explore_noise=0.0, w_threat=5.0)
    safe = ExploreGoal().decide(
        (15, 1), _corridor(), random.Random(1), config, tick=2
    )
    guarded = ExploreGoal().decide(
        (15, 1),
        _corridor(entities={(29, 1): "D"}),
        random.Random(1),
        config,
        tick=2,
    )
    assert safe is not None and guarded is not None
    assert guarded[0] != safe[0] or guarded[0][0] < 29


def test_a_cornered_agent_is_not_asked_again_immediately():
    """Standing down and re-triggering next tick just flickers in and out of
    flight while the agent works its way out of a bad spot."""
    goal = FleeGoal()
    stats = Stats.starting(DEFAULT_CONFIG)
    scary = _corridor(entities={(6, 1): "D"})
    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=10)

    goal.stand_down(cornered_until=10 + DEFAULT_CONFIG.flee_cornered_cooldown)

    assert not goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=11)
    assert not goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=40)
    later = 10 + DEFAULT_CONFIG.flee_cornered_cooldown + 1
    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=later)


def test_an_ordinary_stand_down_carries_no_cooldown():
    goal = FleeGoal()
    stats = Stats.starting(DEFAULT_CONFIG)
    scary = _corridor(entities={(6, 1): "D"})
    goal.active = True
    goal.stand_down()
    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=1)


def test_a_flight_that_never_works_eventually_gives_up():
    """Penned between two threats it can outrun neither of, the agent would
    otherwise run back and forth between them until something killed it."""
    goal = FleeGoal()
    stats = Stats.starting(DEFAULT_CONFIG)
    scary = _corridor(entities={(6, 1): "D"})

    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=100)
    goal.decide((5, 1), scary, DEFAULT_CONFIG, tick=100)
    assert goal.active

    still_early = 100 + DEFAULT_CONFIG.flee_max_ticks - 1
    assert goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=still_early)

    too_long = 100 + DEFAULT_CONFIG.flee_max_ticks + 1
    assert not goal.wants_control((5, 1), scary, stats, DEFAULT_CONFIG, None, tick=too_long)


def test_the_clock_starts_when_the_flight_does():
    goal = FleeGoal()
    scary = _corridor(entities={(6, 1): "D"})
    goal.decide((5, 1), scary, DEFAULT_CONFIG, tick=500)
    assert goal.started_tick == 500
    goal.decide((5, 1), scary, DEFAULT_CONFIG, tick=520)
    assert goal.started_tick == 500, "a continuing flight keeps its original clock"
