"""Start the built executable, draw one frame, and insist it found everything.

Freezing breaks exactly two things, and both fail quietly. A missing font
falls back to pygame's built-in one, and a missing packs folder just means the
texture pack setting has nothing in it - neither raises, so neither would be
noticed until somebody downloaded the zip and wondered why it looked wrong.

So this runs the real exe out of `dist/AsciiCrawler/`, under SDL's dummy video
driver so it needs no screen, and makes it say what it found. `main.py --check`
is the other half.
"""

import os
import subprocess
import sys
from pathlib import Path

TIMEOUT = 180

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "dist" / "AsciiCrawler"


def main() -> int:
    exe = STAGE / "AsciiCrawler.exe"
    if not exe.is_file():
        exe = STAGE / "AsciiCrawler"
    if not exe.is_file():
        print(f"nothing built in {STAGE}; run tools/make_release.py first")
        return 1

    where = os.environ | {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    # Run it from somewhere else entirely: the packs have to be found next to
    # the executable, not next to whoever launched it, and running from the
    # repository root would hide the difference.
    report = ROOT / "dist" / "self-check.txt"
    report.unlink(missing_ok=True)

    # Not `capture_output`: a one-file PyInstaller build is a bootloader that
    # spawns the real program as a child, and both ends of the pipe are
    # inherited. On a timeout `subprocess.run` kills the bootloader and then
    # waits for the pipe to close - which the surviving child never does - so
    # the timeout that was meant to bound this hangs forever instead. It did,
    # on a real runner, for as long as anybody let it.
    #
    # Sending the output to files and waiting on the handle ourselves means a
    # timeout is a kill and nothing else, and the report was going to a file
    # anyway.
    log = ROOT / "dist" / "self-check.log"
    with open(log, "w", encoding="utf-8") as sink:
        started = subprocess.Popen(
            [str(exe), "--check", str(report)],
            env=where,
            cwd=ROOT.parent,
            stdout=sink,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        try:
            code = started.wait(timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            started.kill()
            started.wait()
            print(f"the build did not finish within {TIMEOUT}s; killed it")
            print(_tail(log))
            return 1
    # A windowed build has no stdout, so the file it wrote is the real answer
    # and the log is a bonus - usually pygame's banner, or a traceback if the
    # exe fell over before it could write anything down.
    said = report.read_text(encoding="utf-8") if report.is_file() else ""
    print(said.strip() or "(the build wrote no report)")
    noise = _tail(log)
    if noise:
        print(noise)

    if code != 0:
        print(f"the built game reported a problem (exit {code})")
        return code or 1
    if not said or "MISSING" in said:
        return 1
    print("the build starts, finds its font and sees its packs")
    return 0


def _tail(path, lines: int = 20) -> str:
    """The last of whatever the build printed, if it printed anything."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not text:
        return ""
    return "\n".join(text.splitlines()[-lines:])


if __name__ == "__main__":
    sys.exit(main())
