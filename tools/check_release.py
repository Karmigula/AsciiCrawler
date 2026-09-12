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
    done = subprocess.run(
        [str(exe), "--check", str(report)],
        env=where,
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        timeout=180,
    )
    # A windowed build has no stdout, so the file is the real answer and
    # anything on the pipe is a bonus - usually pygame's banner, or a
    # traceback if the exe failed before it could write anything down.
    said = report.read_text(encoding="utf-8") if report.is_file() else ""
    print(said.strip() or "(the build wrote no report)")
    for stream, target in ((done.stdout, sys.stdout), (done.stderr, sys.stderr)):
        if stream.strip():
            print(stream.strip(), file=target)

    if done.returncode != 0:
        print(f"the built game reported a problem (exit {done.returncode})")
        return done.returncode or 1
    if not said or "MISSING" in said:
        return 1
    print("the build starts, finds its font and sees its packs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
