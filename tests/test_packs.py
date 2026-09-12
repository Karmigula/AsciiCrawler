"""Reading texture packs, and refusing to fall over when one is wrong."""

import json

from render import packs


def _pack(tmp_path, manifest, files=("wall.png",)):
    folder = tmp_path / "mossy"
    folder.mkdir(exist_ok=True)
    for name in files:
        (folder / name).write_bytes(b"not really a png, but it is a file")
    if manifest is not None:
        (folder / packs.MANIFEST).write_text(
            json.dumps(manifest) if isinstance(manifest, dict) else manifest,
            encoding="utf-8",
        )
    return folder


def test_a_pack_maps_glyphs_to_files(tmp_path):
    folder = _pack(tmp_path, {"name": "Mossy", "sprites": {"#": "wall.png"}})

    pack = packs.load(folder)

    assert pack.problems == []
    assert pack.name == "Mossy"
    assert pack.sprite_for("#").path == folder / "wall.png"
    assert pack.sprite_for("#").mode == packs.DEFAULT_MODE


def test_anything_the_pack_leaves_out_stays_ascii(tmp_path):
    """Partial is the normal case, not a broken one."""
    folder = _pack(tmp_path, {"sprites": {"#": "wall.png"}})

    pack = packs.load(folder)

    assert pack.sprite_for("#") is not None
    assert pack.sprite_for("r") is None
    assert pack.sprite_for("@") is None


def test_a_sprite_can_ask_for_its_own_mode(tmp_path):
    folder = _pack(
        tmp_path,
        {
            "mode": "tinted",
            "sprites": {"#": "wall.png", "r": {"file": "rat.png", "mode": "full"}},
        },
        files=("wall.png", "rat.png"),
    )

    pack = packs.load(folder)

    assert pack.problems == []
    assert pack.sprite_for("#").mode == "tinted"
    assert pack.sprite_for("r").mode == "full"


def test_a_missing_folder_is_an_empty_pack_not_a_crash(tmp_path):
    pack = packs.load(tmp_path / "nothing-here")

    assert len(pack) == 0
    assert pack.problems


def test_unreadable_json_is_reported_rather_than_raised(tmp_path):
    folder = _pack(tmp_path, "{ this is not json")

    pack = packs.load(folder)

    assert len(pack) == 0
    assert any("could not be read" in problem for problem in pack.problems)


def test_a_sprite_naming_a_file_that_is_not_there_is_skipped(tmp_path):
    """Reported now rather than as a surprise the first time it is drawn."""
    folder = _pack(tmp_path, {"sprites": {"#": "wall.png", "r": "missing.png"}})

    pack = packs.load(folder)

    assert pack.sprite_for("#") is not None, "the good ones should still load"
    assert pack.sprite_for("r") is None
    assert any("missing.png" in problem for problem in pack.problems)


def test_a_key_that_is_not_one_glyph_is_refused(tmp_path):
    folder = _pack(tmp_path, {"sprites": {"wall": "wall.png", "#": "wall.png"}})

    pack = packs.load(folder)

    assert set(pack.sprites) == {"#"}
    assert any("single glyph" in problem for problem in pack.problems)


def test_an_unknown_mode_falls_back_and_says_so(tmp_path):
    folder = _pack(tmp_path, {"mode": "iridescent", "sprites": {"#": "wall.png"}})

    pack = packs.load(folder)

    assert pack.sprite_for("#").mode == packs.DEFAULT_MODE
    assert any("iridescent" in problem for problem in pack.problems)


def test_a_nonsense_cell_size_is_ignored(tmp_path):
    for value in ("huge", -4, 0):
        folder = _pack(tmp_path, {"cell_size": value, "sprites": {"#": "wall.png"}})

        pack = packs.load(folder)

        assert pack.cell_size == 0, f"{value!r} should have been refused"
        assert pack.problems


def test_a_pack_with_no_sprites_section_is_empty_not_broken(tmp_path):
    folder = _pack(tmp_path, {"name": "Bare"})

    pack = packs.load(folder)

    assert len(pack) == 0
    assert pack.problems


def test_discovery_finds_pack_folders_and_ignores_the_rest(tmp_path):
    good = tmp_path / "mossy"
    good.mkdir()
    (good / packs.MANIFEST).write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "empty").mkdir()

    found = packs.discover(tmp_path)

    assert [folder.name for folder in found] == ["mossy"]


def test_discovery_of_a_folder_that_is_not_there_is_empty(tmp_path):
    assert packs.discover(tmp_path / "no-packs-here") == []


def test_the_ascii_pack_draws_nothing():
    """The way to turn the whole thing off, and the default."""
    assert len(packs.EMPTY) == 0
    assert packs.EMPTY.sprite_for("#") is None


def test_a_sheet_cuts_one_file_into_a_grid(tmp_path):
    """An atlas addresses sprites by counting across and down."""
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "atlas": {"file": "atlas.png", "columns": 4, "sprites": {"#": 0, "r": 5}},
        },
        files=("atlas.png",),
    )

    pack = packs.load(folder)

    assert pack.problems == []
    assert pack.sprite_for("#").rect == (0, 0, 16, 16)
    assert pack.sprite_for("r").rect == (16, 16, 16, 16)
    assert pack.sprite_for("#").path == folder / "atlas.png"


def test_a_pack_can_draw_one_glyph_differently_per_biome(tmp_path):
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "sprites": {"#": "wall.png"},
            "walls": {
                "file": "walls.png",
                "columns": 2,
                "sprites": {"#@frozen": 0, "#@ossuary": 3},
            },
        },
        files=("wall.png", "walls.png"),
    )

    pack = packs.load(folder)

    assert pack.problems == []
    assert pack.sprite_for("#", "frozen").rect == (0, 0, 16, 16)
    assert pack.sprite_for("#", "ossuary").rect == (16, 16, 16, 16)
    # A biome the pack says nothing about still gets the plain wall.
    assert pack.sprite_for("#", "marsh").path == folder / "wall.png"
    assert pack.sprite_for("#").path == folder / "wall.png"


def test_a_biome_wall_with_no_plain_wall_is_still_only_for_that_biome(tmp_path):
    """No accidental promotion: a frozen wall is not every wall."""
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "walls": {"file": "walls.png", "columns": 2, "sprites": {"#@frozen": 0}},
        },
        files=("walls.png",),
    )

    pack = packs.load(folder)

    assert pack.sprite_for("#", "frozen") is not None
    assert pack.sprite_for("#", "halls") is None
    assert pack.sprite_for("#") is None


def test_a_sheet_that_is_not_there_is_reported_not_raised(tmp_path):
    folder = _pack(
        tmp_path,
        {"cell_size": 16, "atlas": {"file": "gone.png", "columns": 4, "sprites": {"#": 0}}},
    )

    pack = packs.load(folder)

    assert len(pack) == 0
    assert any("gone.png" in problem for problem in pack.problems)


def test_a_sheet_without_columns_says_so(tmp_path):
    folder = _pack(
        tmp_path,
        {"cell_size": 16, "atlas": {"file": "atlas.png", "sprites": {"#": 0}}},
        files=("atlas.png",),
    )

    pack = packs.load(folder)

    assert len(pack) == 0
    assert any("columns" in problem for problem in pack.problems)


def test_a_sheet_cell_that_is_not_a_number_is_skipped(tmp_path):
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "atlas": {
                "file": "atlas.png",
                "columns": 4,
                "sprites": {"#": "third", "r": 1},
            },
        },
        files=("atlas.png",),
    )

    pack = packs.load(folder)

    assert pack.sprite_for("#") is None
    assert pack.sprite_for("r") is not None
    assert any("third" in problem for problem in pack.problems)


def test_covers_counts_a_glyph_once_however_many_biomes_it_has(tmp_path):
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "sprites": {"#": "wall.png"},
            "walls": {
                "file": "walls.png",
                "columns": 2,
                "sprites": {"#@frozen": 0, "#@marsh": 1},
            },
        },
        files=("wall.png", "walls.png"),
    )

    pack = packs.load(folder)

    assert pack.covers == "#"
    assert pack.variants == {"#": ["frozen", "marsh"]}


def test_the_starter_pack_ships_a_wall_for_every_biome():
    """The one glyph the game draws most of is worth fifteen of."""
    from pathlib import Path

    from world.biomes import BIOMES

    folder = Path("packs/starter")
    if not (folder / packs.MANIFEST).is_file():
        return  # the pack has not been generated

    pack = packs.load(folder)

    assert pack.problems == []
    missing = [
        biome.key for biome in BIOMES if pack.sprite_for("#", biome.key).biome == ""
    ]
    assert not missing, f"the starter pack has no wall for {missing}"


def test_a_sheet_cell_before_the_start_of_the_sheet_is_refused(tmp_path):
    """Caught at load rather than at draw: a pack reports its faults at once."""
    folder = _pack(
        tmp_path,
        {
            "cell_size": 16,
            "atlas": {"file": "atlas.png", "columns": 2, "sprites": {"#": -3}},
        },
        files=("atlas.png",),
    )

    pack = packs.load(folder)

    assert pack.sprite_for("#") is None
    assert any("-3" in problem for problem in pack.problems)

