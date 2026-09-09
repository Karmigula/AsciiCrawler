from agent.memory import Memory
from render.fog import fog_grid, shade
from world.tiles import Tile


def test_shade_scales_each_channel():
    assert shade((100, 200, 50), 0.5) == (50, 100, 25)


def test_shade_full_factor_is_identity():
    assert shade((13, 200, 77), 1.0) == (13, 200, 77)


def test_fog_grid_full_color_for_visible_cells():
    rows = ["##", "#."]
    palette = {"#": (200, 200, 200), ".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(0, 0), (1, 1)}, {}, 0.6)
    assert grid[0][0] == ("#", (200, 200, 200))
    assert grid[1][1] == (".", (100, 100, 100))


def test_fog_grid_dims_remembered_cells():
    rows = ["##", "#."]
    palette = {"#": (200, 200, 200), ".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(1, 1)}, {(0, 1): 3}, 0.6)
    assert grid[1][0] == ("#", (120, 120, 120))


def test_fog_grid_blanks_never_seen_cells():
    rows = ["##", "#."]
    palette = {"#": (200, 200, 200), ".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(0, 0)}, {(0, 1): 3}, 0.6)
    assert grid[0][1] is None
    assert grid[1][1] is None


def test_fog_grid_visible_takes_priority_over_remembered():
    rows = ["."]
    palette = {".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(0, 0)}, {(0, 0): 3}, 0.6)
    assert grid[0][0] == (".", (100, 100, 100))


def test_fog_grid_reads_the_agents_memory_as_the_known_tier():
    memory = Memory()
    memory.observe({(1, 0): Tile.FLOOR, (0, 1): Tile.WALL}, tick=4)
    rows = ["..", "#."]
    palette = {"#": (200, 200, 200), ".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(0, 0)}, memory, 0.6)
    assert grid[0][0] == (".", (100, 100, 100))  # visible: full color
    assert grid[0][1] == (".", (60, 60, 60))  # remembered: dimmed
    assert grid[1][0] == ("#", (120, 120, 120))  # remembered wall: dimmed
    assert grid[1][1] is None  # never seen: blank


def test_fog_grid_matches_world_coordinates_through_origin():
    """A world-window whose top-left is not (0, 0): global visible/known sets
    are matched against window cells through the origin offset."""
    memory = Memory()
    memory.observe({(102, 51): Tile.FLOOR}, tick=1)
    rows = ["..", ".."]
    palette = {".": (100, 100, 100)}
    grid = fog_grid(rows, palette, {(101, 50)}, memory, 0.6, origin=(101, 50))
    assert grid[0][0] == (".", (100, 100, 100))  # (101, 50) visible
    assert grid[1][1] == (".", (60, 60, 60))  # (102, 51) remembered, dimmed
    assert grid[0][1] is None  # (102, 50) never seen


class _AgeingMemory:
    """Memory stand-in with fixed ages, to pin the tier boundaries exactly."""

    def __init__(self, ages: dict, snapshots: dict | None = None) -> None:
        self._ages = ages
        self._snapshots = snapshots or {}

    def __contains__(self, coord) -> bool:
        return coord in self._ages

    def age(self, coord, tick: int) -> int:
        return self._ages[coord]

    def snapshot(self, coord):
        return self._snapshots.get(coord, (None, None))


PALETTE = {".": (100, 100, 100)}


def _tiers_row(ages: dict, **kwargs):
    known = _AgeingMemory(ages)
    return fog_grid(
        ["...."],
        PALETTE,
        {(0, 0)},
        known,
        0.6,
        tick=1000,
        ttl=100,
        stale_factor=0.35,
        stale_fraction=0.5,
        **kwargs,
    )[0]


def test_the_four_fog_tiers_map_to_four_brightnesses():
    """visible -> full, fresh -> 60%, stale -> 35%, expired -> blank."""
    row = _tiers_row({(0, 0): 0, (1, 0): 10, (2, 0): 80, (3, 0): 500})
    assert row[0] == (".", (100, 100, 100))  # visible
    assert row[1] == (".", (60, 60, 60))  # fresh
    assert row[2] == (".", (35, 35, 35))  # stale
    assert row[3] is None  # expired: unknown again


def test_a_tile_that_was_never_seen_is_blank_like_an_expired_one():
    row = _tiers_row({(0, 0): 0})
    assert row[2] is None


def test_the_stale_boundary_sits_at_the_configured_fraction_of_ttl():
    row = _tiers_row({(1, 0): 50, (2, 0): 51})
    assert row[1] == (".", (60, 60, 60))  # exactly at the fraction: still fresh
    assert row[2] == (".", (35, 35, 35))


def test_expiry_blanks_a_tile_before_the_pruner_gets_to_it():
    """Decay is rendered on age, not on whether a sweep has run yet."""
    row = _tiers_row({(1, 0): 101})
    assert row[1] is None


def test_without_a_ttl_the_old_two_tier_behaviour_is_unchanged():
    known = _AgeingMemory({(0, 0): 0, (1, 0): 10_000})
    row = fog_grid(["..."], PALETTE, {(0, 0)}, known, 0.6)[0]
    assert row[0] == (".", (100, 100, 100))
    assert row[1] == (".", (60, 60, 60))  # ancient, but nothing said it expires
    assert row[2] is None


def test_remembered_entities_render_as_dim_ghosts_at_their_last_position():
    known = _AgeingMemory(
        {(0, 0): 0, (1, 0): 10, (2, 0): 80},
        {(0, 0): ("r", None), (1, 0): ("g", None), (2, 0): (None, "!")},
    )
    row = fog_grid(
        ["..."],
        PALETTE,
        {(0, 0)},
        known,
        0.6,
        tick=1000,
        ttl=100,
        stale_factor=0.35,
        ghost_color=(150, 150, 160),
    )[0]
    assert row[0] == ("r", (150, 150, 160))  # visible: full-strength
    assert row[1] == ("g", (90, 90, 96))  # remembered: dimmed by its tier
    assert row[2] == ("!", (52, 52, 56))  # stale item ghost


def test_an_expired_ghost_disappears_with_its_tile():
    known = _AgeingMemory({(1, 0): 500}, {(1, 0): ("D", None)})
    row = fog_grid(["..."], PALETTE, {(0, 0)}, known, 0.6, tick=1000, ttl=100)[0]
    assert row[1] is None
