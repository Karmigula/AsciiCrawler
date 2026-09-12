# PyInstaller build of the desktop game. Driven by tools/make_release.py.
#
# One file, because a release you can double-click without reading anything is
# the point. The font goes inside it; the texture packs deliberately do not -
# `tools/make_release.py` puts those next to the exe, where somebody can add
# to them. `paths.py` is what keeps the two straight at runtime.
#
# `web/`, `tools/` and the test suite are excluded: FastAPI, uvicorn and
# pytest have no business in a game window, and leaving them in roughly
# doubles the download.

block_cipher = None

analysis = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets/fonts/IBMPlexMono-Regular.ttf", "assets/fonts")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "fastapi",
        "starlette",
        "uvicorn",
        "pytest",
        "_pytest",
        "tkinter",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="AsciiCrawler",
    # The creature itself, drawn by tools/make_icon.py from the same `@` the
    # starter pack uses. Without this the download wears PyInstaller's icon,
    # which tells the person who unzipped it nothing about what they have.
    icon="assets/icon.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # No console behind the window. `paths.note` is the reason that is safe:
    # a windowed build has no stdout, and printing to it would otherwise take
    # the game down over something as small as a typo in a pack manifest.
    console=False,
    # A windowed build that raises on startup otherwise pops a modal dialog
    # nobody can see and waits for someone to click it. On a build runner that
    # is a hang; on a player's machine it is a game that never opens and never
    # says why. With this the process dies and writes the traceback to stderr,
    # which is where `tools/check_release.py` is already looking.
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
