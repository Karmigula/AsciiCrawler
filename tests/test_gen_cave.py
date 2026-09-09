import random

from config import DEFAULT_CONFIG
from world.gen_cave import generate
from world.tiles import Tile


def _gen(seed: int):
    cfg = DEFAULT_CONFIG
    return generate(
        random.Random(seed),
        cfg.chunk_size,
        cfg.chunk_size,
        cfg.cave_fill_prob,
        cfg.cave_smooth_steps,
        cfg.cave_wall_threshold,
    )


def test_cave_same_seed_produces_identical_grids():
    assert _gen(42).tobytes() == _gen(42).tobytes()


def test_cave_different_seeds_produce_different_grids():
    assert _gen(1).tobytes() != _gen(2).tobytes()


def test_cave_dimensions_match_request():
    tiles = _gen(42)
    assert tiles.shape == (
        DEFAULT_CONFIG.chunk_size,
        DEFAULT_CONFIG.chunk_size,
    )


def test_cave_outer_border_is_all_wall():
    tiles = _gen(42).tolist()
    size = DEFAULT_CONFIG.chunk_size
    assert all(tile == int(Tile.WALL) for tile in tiles[0])
    assert all(tile == int(Tile.WALL) for tile in tiles[size - 1])
    assert all(row[0] == int(Tile.WALL) for row in tiles)
    assert all(row[size - 1] == int(Tile.WALL) for row in tiles)


def test_cave_floor_fraction_is_sane_across_seeds():
    """Measured 0.57-0.66 on defaults; bounds hold with wide margin."""
    fractions = []
    for seed in range(10):
        tiles = _gen(seed)
        fractions.append(float((tiles == int(Tile.FLOOR)).mean()))
    assert all(0.3 < f < 0.8 for f in fractions)
