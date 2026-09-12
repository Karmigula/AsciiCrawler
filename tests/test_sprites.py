"""Drawing a texture pack: the half that needs pygame.

Runs under SDL's dummy video driver, so it draws into memory and reads the
pixels back. Checking that a sprite *loaded* would prove very little; what
matters is that the right thing ends up on the screen and that everything the
pack leaves alone still comes out as a letter.
"""

import json
import os

import pytest

pygame = pytest.importorskip("pygame")


@pytest.fixture(scope="module", autouse=True)
def _headless():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield


def _pack_folder(tmp_path, entries, colours=None):
    """Write a pack of flat-coloured squares and its manifest."""
    folder = tmp_path / "probe"
    folder.mkdir(exist_ok=True)
    colours = colours or {}
    for glyph, entry in entries.items():
        name = entry if isinstance(entry, str) else entry["file"]
        square = pygame.Surface((16, 16), pygame.SRCALPHA)
        square.fill(colours.get(glyph, (255, 255, 255, 255)))
        pygame.image.save(square, str(folder / name))
    (folder / "pack.json").write_text(
        json.dumps({"name": "Probe", "sprites": entries}), encoding="utf-8"
    )
    return folder


def _screen():
    from config import DEFAULT_CONFIG
    from render.screen import Screen

    return Screen(DEFAULT_CONFIG), DEFAULT_CONFIG


def _pixel(screen, config, column):
    """A pixel inside the given cell of the top row."""
    return screen._window.get_at((10 + column * config.cell_size, 10))[:3]


def test_a_sprite_replaces_the_letter(tmp_path):
    from render.packs import load

    folder = _pack_folder(
        tmp_path,
        {"#": {"file": "wall.png", "mode": "full"}},
        {"#": (255, 0, 255, 255)},
    )
    screen, config = _screen()
    cells = [[("#", (200, 200, 200))]]

    screen.draw_cells(cells)
    as_ascii = _pixel(screen, config, 0)
    screen.use_pack(load(folder))
    screen.draw_cells(cells)

    assert _pixel(screen, config, 0) == (255, 0, 255)
    assert _pixel(screen, config, 0) != as_ascii


def test_anything_the_pack_leaves_out_is_still_drawn_as_a_letter(tmp_path):
    """The whole point of the feature: a pack need not cover everything."""
    from render.packs import load

    folder = _pack_folder(tmp_path, {"#": "wall.png"}, {"#": (255, 0, 255, 255)})
    screen, config = _screen()
    cells = [[("#", (200, 200, 200)), ("r", (150, 150, 150))]]

    screen.draw_cells(cells)
    rat_as_ascii = _pixel(screen, config, 1)
    screen.use_pack(load(folder))
    screen.draw_cells(cells)

    assert _pixel(screen, config, 1) == rat_as_ascii, "the rat lost its letter"


def test_tinted_art_takes_the_colour_of_the_cell(tmp_path):
    """Which is how a greyscale pack inherits fog, biome and overlays."""
    from render.packs import load

    folder = _pack_folder(tmp_path, {".": "floor.png"}, {".": (255, 255, 255, 255)})
    screen, config = _screen()
    screen.use_pack(load(folder))

    screen.draw_cells([[(".", (90, 40, 20))]])

    assert _pixel(screen, config, 0) == (90, 40, 20)


def test_full_colour_art_keeps_its_colours_and_is_only_dimmed(tmp_path):
    from render.packs import load

    folder = _pack_folder(
        tmp_path, {"#": {"file": "wall.png", "mode": "full"}}, {"#": (200, 100, 50, 255)}
    )
    screen, config = _screen()
    screen.use_pack(load(folder))
    cells = [[("#", (10, 10, 10))]]

    screen.draw_cells(cells, shades=[[1.0]])
    lit = _pixel(screen, config, 0)
    screen.draw_cells(cells, shades=[[0.4]])
    remembered = _pixel(screen, config, 0)

    assert lit == (200, 100, 50), "it did not keep its own colours"
    assert all(dim < full for dim, full in zip(remembered, lit)), "it was not dimmed"


def test_handing_back_an_empty_pack_returns_to_letters(tmp_path):
    from render.packs import EMPTY, load

    folder = _pack_folder(tmp_path, {"#": "wall.png"}, {"#": (255, 0, 255, 255)})
    screen, config = _screen()
    cells = [[("#", (200, 200, 200))]]

    screen.draw_cells(cells)
    as_ascii = _pixel(screen, config, 0)
    screen.use_pack(load(folder))
    screen.draw_cells(cells)
    assert _pixel(screen, config, 0) != as_ascii

    screen.use_pack(EMPTY)
    screen.draw_cells(cells)

    assert _pixel(screen, config, 0) == as_ascii


def test_a_sprite_that_will_not_load_costs_one_glyph_and_not_the_game(tmp_path):
    """A texture pack must never be able to stop the game starting."""
    from render.packs import load

    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "wall.png").write_bytes(b"this is not a png")
    (folder / "pack.json").write_text(
        json.dumps({"sprites": {"#": "wall.png"}}), encoding="utf-8"
    )
    screen, config = _screen()
    screen.use_pack(load(folder))
    cells = [[("#", (200, 200, 200))]]

    screen.draw_cells(cells)  # must not raise
    drawn = _pixel(screen, config, 0)
    screen.use_pack(None)
    screen.draw_cells(cells)

    assert drawn == _pixel(screen, config, 0), "it should have fallen back to the letter"
    assert screen._sheet is None or screen._sheet.failures


def test_sprites_are_scaled_once_and_kept(tmp_path):
    """Scaling every tile every frame turns the aquarium into a slideshow."""
    from render.packs import load
    from render.sprites import SpriteSheet

    folder = _pack_folder(tmp_path, {"#": "wall.png"})
    sheet = SpriteSheet(load(folder), 20)

    first = sheet.for_glyph("#")
    again = sheet.for_glyph("#")

    assert first is again, "it was rebuilt rather than cached"
    assert first.get_size() == (20, 20), "it was not scaled to the cell"


def test_a_resize_throws_the_scaled_copies_away(tmp_path):
    from render.packs import load
    from render.sprites import SpriteSheet

    folder = _pack_folder(tmp_path, {"#": "wall.png"})
    sheet = SpriteSheet(load(folder), 20)
    small = sheet.for_glyph("#")

    sheet.resize(32)
    big = sheet.for_glyph("#")

    assert small.get_size() == (20, 20)
    assert big.get_size() == (32, 32)


def test_asking_for_a_glyph_the_pack_does_not_have_is_cheap(tmp_path):
    """It is asked once per drawn tile, so the miss has to be a dict lookup."""
    from render.packs import load
    from render.sprites import SpriteSheet

    sheet = SpriteSheet(load(_pack_folder(tmp_path, {"#": "wall.png"})), 20)

    assert sheet.for_glyph("r") is None
    assert sheet.for_glyph("r") is None  # and still None the second time


def test_the_starter_pack_redraws_a_real_frame():
    """End to end: a real world, a real frame, the shipped pack.

    The unit tests above all draw one contrived cell. This one takes a world
    that has been running for a while and checks the window actually changes,
    which is the only claim anybody cares about.
    """
    from dataclasses import replace
    from pathlib import Path

    from config import DEFAULT_CONFIG
    from render.frame import build_frame
    from render.packs import EMPTY, load
    from render.screen import Screen
    from sim.session import Session

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    config = replace(DEFAULT_CONFIG, texture_pack="starter")
    session = Session(config, seed=3, record_hall=False)
    session.advance(150)
    screen = Screen(config)
    origin = screen.camera_origin((session.agent.x, session.agent.y))
    cols, rows = screen.view_dims
    size = config.cell_size

    def sample(pack):
        screen.use_pack(pack)
        shades: list = []
        cells, backgrounds, _ = build_frame(
            session.world, session.agent, config, origin, cols, rows, shades_out=shades
        )
        screen.draw_cells(cells, backgrounds, shades)
        middle_row, middle_col = rows // 2, cols // 2
        return [
            screen._window.get_at((col * size + dx, row * size + dy))[:3]
            for row in range(middle_row - 4, middle_row + 4)
            for col in range(middle_col - 6, middle_col + 6)
            for dx, dy in ((3, 3), (10, 10), (16, 16))
        ]

    as_letters = sample(EMPTY)
    pack = load(folder)
    assert pack.problems == [], pack.problems
    dressed = sample(pack)

    assert len(set(dressed)) > len(set(as_letters)), "the pack added no detail"
    changed = sum(1 for a, b in zip(as_letters, dressed) if a != b)
    assert changed > len(as_letters) // 2, f"only {changed} pixels changed"


def test_the_starter_pack_covers_the_ground_and_the_living_things():
    from pathlib import Path

    from render.packs import load
    from sim.monsters import MONSTERS
    from world.tiles import Tile

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    pack = load(folder)

    for tile in Tile:
        assert pack.sprite_for(tile.glyph) is not None, f"{tile.name} has no sprite"
    for kind in MONSTERS:
        assert pack.sprite_for(kind.glyph) is not None, f"{kind.key} has no sprite"
    assert pack.sprite_for("@") is not None, "the creature itself has no sprite"


def test_the_starter_pack_still_leaves_plenty_as_letters():
    """A pack need not be finished to be usable, and this one is not.

    Totems, stalls, graves, the gear on the floor and every named boss are
    still letters, which is the demonstration that partial is normal rather
    than an unfinished state somebody has to apologise for.
    """
    from pathlib import Path

    from render.packs import load
    from sim.bosses import BOSSES

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    pack = load(folder)

    for glyph in ("&", "%", "+", ")", "[", "=", '"'):
        assert pack.sprite_for(glyph) is None, f"{glyph} should still be a letter"
    for boss in BOSSES:
        assert pack.sprite_for(boss.glyph) is None, f"{boss.key} should be a letter"


def test_every_creature_has_its_own_silhouette():
    """Colour is already spoken for: a monster is tinted by how dangerous it is.

    So two creatures that differ only in colour are the same creature on
    screen, and the shapes have to carry the identity by themselves.
    """
    from pathlib import Path

    from render.packs import load
    from render.sprites import SpriteSheet
    from sim.monsters import MONSTERS

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    sheet = SpriteSheet(load(folder), 16)
    shapes = {}
    for glyph in [kind.glyph for kind in MONSTERS] + ["@"]:
        art = sheet.for_glyph(glyph)
        # The silhouette alone: where the sprite is solid, ignoring brightness.
        mask = frozenset(
            (x, y)
            for x in range(16)
            for y in range(16)
            if art.get_at((x, y))[3] > 40
        )
        assert len(mask) > 20, f"{glyph} is nearly empty"
        for other, seen in shapes.items():
            # Intersection over union, not over the smaller shape: a small
            # figure standing inside a big blob's outline scores 94% by that
            # measure while looking nothing like it, which is how this test
            # first accused the creature of being an ogre.
            overlap = len(mask & seen) / max(1, len(mask | seen))
            assert overlap < 0.75, f"{glyph} and {other} are the same shape"
        shapes[glyph] = mask
