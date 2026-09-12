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


def test_the_starter_pack_covers_every_glyph_the_game_draws():
    """It is finished now, and this is what finished means.

    Built from the same registries the cheat sheet is, so a new monster, tile
    or boss fails here until somebody draws it - which is the useful failure,
    since the alternative is one lonely letter among the sprites that nobody
    notices for a month.
    """
    from pathlib import Path

    from config import DEFAULT_CONFIG
    from render.legend import legend_sections
    from render.packs import load
    from sim.spells import BOLT_GLYPHS

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    pack = load(folder)
    drawable = {
        glyph for _heading, rows in legend_sections(DEFAULT_CONFIG) for glyph, _, _ in rows
    } | set(BOLT_GLYPHS.values())

    missing = sorted(glyph for glyph in drawable if pack.sprite_for(glyph) is None)
    assert not missing, f"the starter pack has no sprite for {missing}"


def test_the_pack_invents_nothing_the_game_never_draws():
    """The other direction: art for a glyph that cannot appear is dead weight."""
    from pathlib import Path

    from config import DEFAULT_CONFIG
    from render.legend import legend_sections
    from render.packs import load
    from sim.spells import BOLT_GLYPHS

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    pack = load(folder)
    drawable = {
        glyph for _heading, rows in legend_sections(DEFAULT_CONFIG) for glyph, _, _ in rows
    } | set(BOLT_GLYPHS.values())

    # `covers` rather than the keys: a biome variant is art for a glyph the
    # game does draw, not art for a glyph called `#@frozen`.
    assert not sorted(set(pack.covers) - drawable)
    assert set(pack.variants) <= drawable


def test_every_creature_has_its_own_silhouette():
    """Colour is already spoken for: a monster is tinted by how dangerous it is.

    So two creatures that differ only in colour are the same creature on
    screen, and the shapes have to carry the identity by themselves.
    """
    from pathlib import Path

    from render.packs import load
    from render.sprites import SpriteSheet
    from sim.bosses import BOSSES
    from sim.monsters import MONSTERS

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    sheet = SpriteSheet(load(folder), 16)
    shapes = {}
    everything = (
        [kind.glyph for kind in MONSTERS] + [boss.glyph for boss in BOSSES] + ["@"]
    )
    for glyph in everything:
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


def _legend_screen(pack_name, size):
    from dataclasses import replace

    from config import DEFAULT_CONFIG
    from render.legend import legend_rows
    from render.menu import block_text
    from render.packs import EMPTY, load
    from render.screen import Screen

    config = replace(
        DEFAULT_CONFIG,
        texture_pack=pack_name,
        window_width=size[0],
        window_height=size[1],
    )
    screen = Screen(config)
    screen.use_pack(load("packs/starter") if pack_name else EMPTY)
    screen.draw_legend(legend_rows(config), config, block_text("LEGEND"))
    # A copy, because `set_mode` hands back the one display surface: two
    # Screens share it, and the second draw silently overwrites the first.
    # Comparing the live surfaces made this test compare a picture with
    # itself, which it duly reported as "no difference".
    return screen, config, screen._window.copy()


def test_the_symbol_sheet_fits_the_window_it_is_drawn_in():
    """It ran off the bottom: fifty-one entries in one uncliped column."""
    from pathlib import Path

    if not Path("packs/starter/pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    for size in ((1200, 800), (1000, 620), (900, 520)):
        _screen, config, window = _legend_screen("starter", size)
        background = config.background_color[:3]
        # Nothing at all in the last few rows of pixels: the footer sits above
        # them, and anything below the footer is content that fell off.
        for y in range(window.get_height() - 6, window.get_height()):
            for x in range(0, window.get_width(), 7):
                assert window.get_at((x, y))[:3] == background, (
                    f"something was drawn at the very bottom edge at {size}"
                )


def test_the_symbol_sheet_shows_what_a_pack_actually_draws():
    """A sheet saying a wall is `#` while the screen is full of brickwork is
    not a legend, it is a quiz."""
    from pathlib import Path

    if not Path("packs/starter/pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    _a, _c, dressed = _legend_screen("starter", (1200, 800))
    _b, _d, plain = _legend_screen("", (1200, 800))

    differing = sum(
        1
        for y in range(170, 760, 3)
        for x in range(260, 620, 3)
        if dressed.get_at((x, y)) != plain.get_at((x, y))
    )
    assert differing > 50, "the sheet looks the same with a pack on"


def test_a_wall_looks_different_in_different_biomes(tmp_path):
    """The whole point of per-biome art: two cells, two pictures, one glyph."""
    from render.packs import load

    folder = tmp_path / "biomed"
    folder.mkdir()
    sheet = pygame.Surface((32, 16), pygame.SRCALPHA)
    sheet.fill((255, 0, 0, 255), (0, 0, 16, 16))
    sheet.fill((0, 0, 255, 255), (16, 0, 16, 16))
    pygame.image.save(sheet, str(folder / "walls.png"))
    plain = pygame.Surface((16, 16), pygame.SRCALPHA)
    plain.fill((0, 255, 0, 255))
    pygame.image.save(plain, str(folder / "wall.png"))
    (folder / "pack.json").write_text(
        json.dumps(
            {
                "name": "Biomed",
                "cell_size": 16,
                "mode": "full",
                "sprites": {"#": "wall.png"},
                "walls": {
                    "file": "walls.png",
                    "columns": 2,
                    "sprites": {"#@frozen": 0, "#@marsh": 1},
                },
            }
        ),
        encoding="utf-8",
    )

    screen, config = _screen()
    screen.use_pack(load(folder))
    screen.draw_cells(
        [[("#", (255, 255, 255)), ("#", (255, 255, 255)), ("#", (255, 255, 255))]],
        biomes=[["frozen", "marsh", "ruins"]],
    )

    assert _pixel(screen, config, 0) == (255, 0, 0)
    assert _pixel(screen, config, 1) == (0, 0, 255)
    # A biome the pack knows nothing about falls back to the plain wall.
    assert _pixel(screen, config, 2) == (0, 255, 0)

    # And without the grid it is the plain wall everywhere - which is what a
    # caller that never heard of biomes gets, and is also the only thing that
    # proves the three answers above came from the grid and not from luck.
    screen.draw_cells([[("#", (255, 255, 255))] * 3])
    assert [_pixel(screen, config, at) for at in range(3)] == [(0, 255, 0)] * 3


def test_one_sheet_is_opened_once_however_many_sprites_come_out_of_it(tmp_path):
    """The reason for an atlas: fifty-one glyphs, one file handle."""
    from render.packs import load
    from render.sprites import SpriteSheet

    folder = tmp_path / "atlased"
    folder.mkdir()
    art = pygame.Surface((32, 32), pygame.SRCALPHA)
    art.fill((200, 200, 200, 255))
    pygame.image.save(art, str(folder / "atlas.png"))
    (folder / "pack.json").write_text(
        json.dumps(
            {
                "cell_size": 16,
                "atlas": {
                    "file": "atlas.png",
                    "columns": 2,
                    "sprites": {"#": 0, "r": 1, "@": 2, "o": 3},
                },
            }
        ),
        encoding="utf-8",
    )

    sheet = SpriteSheet(load(folder), 16)
    loads = []
    original = pygame.image.load

    def counted(name):
        loads.append(name)
        return original(name)

    pygame.image.load = counted
    try:
        for glyph in "#r@o":
            assert sheet.for_glyph(glyph) is not None
    finally:
        pygame.image.load = original

    assert len(loads) == 1


def test_a_cell_off_the_edge_of_its_sheet_costs_that_glyph_and_says_so(tmp_path):
    from render.packs import load
    from render.sprites import SpriteSheet

    folder = tmp_path / "overrun"
    folder.mkdir()
    art = pygame.Surface((32, 16), pygame.SRCALPHA)
    art.fill((200, 200, 200, 255))
    pygame.image.save(art, str(folder / "atlas.png"))
    (folder / "pack.json").write_text(
        json.dumps(
            {
                "cell_size": 16,
                "atlas": {
                    "file": "atlas.png",
                    "columns": 2,
                    "sprites": {"#": 0, "r": 9},
                },
            }
        ),
        encoding="utf-8",
    )

    sheet = SpriteSheet(load(folder), 16)

    assert sheet.for_glyph("#") is not None
    assert sheet.for_glyph("r") is None
    assert any("atlas.png" in failure for failure in sheet.failures)


def test_the_starter_pack_draws_fifteen_different_walls():
    """One rock shape per biome, and no two the same."""
    from pathlib import Path

    from render.packs import load
    from render.sprites import SpriteSheet
    from world.biomes import BIOMES

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    sheet = SpriteSheet(load(folder), 32)
    shapes = {}
    for biome in BIOMES:
        art = sheet.for_glyph("#", biome.key)
        assert art is not None, f"no wall for {biome.key}"
        pixels = tuple(
            art.get_at((x, y))[:3] for x in range(0, 32, 2) for y in range(0, 32, 2)
        )
        clash = [key for key, seen in shapes.items() if seen == pixels]
        assert not clash, f"{biome.key} draws the same wall as {clash[0]}"
        shapes[biome.key] = pixels


def test_a_biome_wall_is_bright_enough_to_survive_being_tinted():
    """Tinted art is multiplied, so mid-grey rock comes out near black."""
    from pathlib import Path

    from render.packs import load
    from render.sprites import SpriteSheet
    from world.biomes import BIOMES

    folder = Path("packs/starter")
    if not (folder / "pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    sheet = SpriteSheet(load(folder), 32)
    for biome in BIOMES:
        art = sheet.for_glyph("#", biome.key)
        lit = [
            art.get_at((x, y))[0]
            for x in range(32)
            for y in range(32)
            if art.get_at((x, y))[3] > 40
        ]
        average = sum(lit) / max(1, len(lit))
        assert average > 120, f"{biome.key} averages {average:.0f}; it will go black"


def test_the_biome_grid_lines_up_with_the_cells_it_describes():
    """The grid the pack reads has to be the same window as the glyphs.

    An off-by-one here would draw the frozen wall one row into the ossuary and
    nothing would ever complain: both are walls, both are grey, and the screen
    would simply be subtly wrong forever.
    """
    from dataclasses import replace
    from pathlib import Path

    from config import DEFAULT_CONFIG
    from render.frame import build_frame
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

    biomes: list = []
    cells, _backgrounds, _ = build_frame(
        session.world, session.agent, config, origin, cols, rows, biomes_out=biomes
    )

    assert len(biomes) == rows
    assert all(len(line) == cols for line in biomes)
    assert len(biomes) == len(cells)
    for y, line in enumerate(biomes):
        for x, key in enumerate(line):
            assert key == session.world.biome_key_at(origin[0] + x, origin[1] + y)


def test_a_caller_that_wants_no_biome_grid_pays_for_none():
    """`biomes_out` is opt-in, like `shades_out`: the web build asks for neither."""
    from pathlib import Path

    from config import DEFAULT_CONFIG
    from render.frame import build_frame
    from sim.session import Session

    if not Path("packs/starter/pack.json").is_file():
        pytest.skip("the starter pack has not been generated")

    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(20)

    cells, backgrounds, text = build_frame(
        session.world, session.agent, DEFAULT_CONFIG, (0, 0), 12, 8
    )

    assert len(cells) == 8
    assert len(backgrounds) == 8
    assert len(text) == 8

