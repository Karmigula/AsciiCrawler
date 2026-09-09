from render.fog import fog_grid, shade


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
