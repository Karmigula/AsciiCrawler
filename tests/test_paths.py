"""Where the game looks for things, frozen and not.

The whole of this module is about one distinction that only exists in a built
executable: a bundled file is unpacked to a temporary folder that is deleted
on exit, and a file beside the exe is not. Getting it backwards loses the
player's hall of fame every time they close the game, and from source both
answers are the repository, so nothing here would ever show up in ordinary
use. Hence tests that lie about being frozen.
"""

import sys
from pathlib import Path

import paths


def _freeze(monkeypatch, unpacked, exe):
    """Pretend to be a PyInstaller build, the way PyInstaller announces one."""
    monkeypatch.setattr(paths, "FROZEN", True)
    monkeypatch.setattr(sys, "_MEIPASS", str(unpacked), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))


def test_from_source_both_answers_are_the_repository():
    """Nothing moves for anybody running `python main.py`."""
    here = Path(paths.__file__).resolve().parent

    assert paths.bundled("packs") == here / "packs"
    assert paths.beside("packs") == here / "packs"


def test_frozen_reads_bundled_files_out_of_the_unpacked_folder(monkeypatch, tmp_path):
    _freeze(monkeypatch, tmp_path / "unpacked", tmp_path / "game" / "AsciiCrawler.exe")

    found = paths.bundled("assets/fonts/IBMPlexMono-Regular.ttf")

    assert found.parent.parent.parent == tmp_path / "unpacked"


def test_frozen_keeps_the_players_own_files_next_to_the_exe(monkeypatch, tmp_path):
    """The one that matters: these have to outlive the process, and the exe."""
    _freeze(monkeypatch, tmp_path / "unpacked", tmp_path / "game" / "AsciiCrawler.exe")

    for owned in ("packs", "settings.json", "hall_of_fame.json"):
        assert paths.beside(owned).parent == tmp_path / "game"


def test_the_two_never_agree_when_frozen(monkeypatch, tmp_path):
    """If they did, one of them would be wrong."""
    _freeze(monkeypatch, tmp_path / "unpacked", tmp_path / "game" / "AsciiCrawler.exe")

    assert paths.bundled("packs") != paths.beside("packs")


def test_a_note_with_nowhere_to_print_is_not_a_crash(monkeypatch):
    """A windowed build has no stdout, and a pack typo must not end the game."""
    monkeypatch.setattr(sys, "stdout", None)

    paths.note("a texture pack is wrong")  # the assertion is that this returns


def test_a_note_prints_when_there_is_somewhere_to_print(capsys):
    paths.note("hello")

    assert capsys.readouterr().out.strip() == "hello"


def test_the_saved_files_are_the_ones_that_live_beside_the_game():
    """Guards the wiring, not the module: these are easy to point anywhere."""
    import settings_store
    from sim import hall

    home = paths.beside(".").resolve()

    assert Path(settings_store.DEFAULT_PATH).resolve().parent == home
    assert Path(hall.DEFAULT_PATH).resolve().parent == home


def test_the_version_is_one_number_in_one_place():
    """The title screen, the zip name and the git tag all read this."""
    from config import DEFAULT_CONFIG
    from render.menu import menu_lines
    from version import VERSION

    shown = [text for text, _colour in menu_lines(0, 1, DEFAULT_CONFIG)]

    assert f"version {VERSION}" in shown

