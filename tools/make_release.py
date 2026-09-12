"""Build the release: one executable, with a packs folder next to it.

    .venv\\Scripts\\python.exe tools/make_release.py

Leaves `dist/AsciiCrawler/` looking like this, and a zip of it beside:

    AsciiCrawler.exe
    packs/starter/        atlas.png, walls.png, pack.json
    README.txt

The split is deliberate. The exe holds the code and the font, which nobody
should have to think about. The `packs` folder is outside it because the whole
point of texture packs is that somebody can add one - a pack sealed inside the
executable is a pack nobody can replace. `paths.py` is the other half of that
arrangement: `bundled` reads out of the exe, `beside` reads next to it.

Nothing this writes is committed. The zip is what goes on a GitHub release,
which is why `dist/` and `build/` are ignored.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
STAGE = DIST / "AsciiCrawler"
NAME = "AsciiCrawler"

# Everything the player is meant to be able to open, edit or delete. The font
# is not here on purpose: it goes inside the exe, in the spec.
ALONGSIDE = ("packs",)

READ_ME = """AsciiCrawler
============

Nobody plays this. You watch it.

Run AsciiCrawler.exe. There is no installer, and nothing is written outside
this folder.

The title screen has everything on it: watch, a new world, settings, a soak
test, and the hall of fame. Arrow keys and enter; esc goes back, and from the
title screen esc closes the window.

While it is running
-------------------

  esc        back to the title screen
  space      pause
  1 2 3      speed: 1x, 4x, 16x
  n          a new world, fresh seed and fresh creature
  b          what is in its bag
  j          what every symbol means
  h          hide the HUD
  p          screenshot
  F1 - F5    overlays: what it sees, remembers, fears, plans, is drawn to
  F10 / F11  borderless window / borderless fullscreen

Texture packs
-------------

The `packs` folder next to this file is read when the game starts, and every
folder in it holding a `pack.json` turns up under settings. `starter` is the
one that ships.

A pack does not have to replace everything. Whatever it leaves out is drawn as
a letter instead, so a pack that only redraws walls is a perfectly good pack.
The format, and how to build one, is in the README at

    https://github.com/Karmigula/AsciiCrawler

Your files
----------

`settings.json`, `hall_of_fame.json` and any screenshots are written into this
folder, never anywhere else on the machine. Copy them across to keep your hall
of fame when a new version comes out; delete them to start clean.
"""


def _run(command) -> None:
    print(" ".join(str(part) for part in command))
    subprocess.run(command, check=True, cwd=ROOT)


def build() -> Path:
    """PyInstaller, then arrange the folder, then zip it."""
    if shutil.which("pyinstaller") is None and not _importable("PyInstaller"):
        raise SystemExit(
            "pyinstaller is not installed in this environment.\n"
            "    .venv\\Scripts\\python.exe -m pip install pyinstaller"
        )

    starter = ROOT / "packs" / "starter" / "pack.json"
    if not starter.is_file():
        # A release whose one shipped pack is missing is worse than no release:
        # the texture pack setting would be there with nothing to choose.
        raise SystemExit(
            "packs/starter is not built.\n"
            "    .venv\\Scripts\\python.exe -m tools.make_starter_pack"
        )

    icon = ROOT / "assets" / "icon.ico"
    if not icon.is_file():
        # Committed, but generated - so a checkout that has lost it builds it
        # rather than failing, and a release never goes out unbranded.
        print(f"{icon} is missing; drawing it")
        _run([sys.executable, "-m", "tools.make_icon"])

    for folder in (DIST, ROOT / "build"):
        shutil.rmtree(folder, ignore_errors=True)

    _run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "AsciiCrawler.spec"])

    exe = DIST / f"{NAME}.exe"
    if not exe.is_file():  # a non-Windows build has no suffix
        exe = DIST / NAME
    if not exe.is_file():
        raise SystemExit(f"PyInstaller produced no executable in {DIST}")

    STAGE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(exe), STAGE / exe.name)
    for folder in ALONGSIDE:
        # Archives are skipped: a zip of a pack sitting inside that same pack
        # is somebody's working copy, not art, and shipping it would double
        # the folder's size for nothing.
        shutil.copytree(
            ROOT / folder,
            STAGE / folder,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("*.zip", "*.7z", "*.rar", "__pycache__"),
        )
    (STAGE / "README.txt").write_text(READ_ME, encoding="utf-8")

    archive = DIST / f"{NAME}-{_version()}-windows.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in sorted(STAGE.rglob("*")):
            if item.is_file():
                bundle.write(item, item.relative_to(DIST))
    return archive


def _importable(name: str) -> bool:
    from importlib.util import find_spec

    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _version() -> str:
    """The tag being released, or what `version.py` says.

    Actions sets GITHUB_REF_NAME to the tag, and a tag is the more specific
    claim - it is the thing somebody can check out again. A build by hand has
    no tag, so it falls back to the number the title screen shows.
    """
    tag = os.environ.get("GITHUB_REF_NAME")
    if tag:
        return tag.removeprefix("v")

    sys.path.insert(0, str(ROOT))
    from version import VERSION

    return VERSION


def main() -> None:
    archive = build()
    size = archive.stat().st_size / 1_000_000
    print(f"\n{archive}  ({size:.1f} MB)")
    print(f"unzipped, that is {NAME} and a packs folder it can see.")


if __name__ == "__main__":
    main()
