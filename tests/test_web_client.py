"""The browser's half of the frame contract.

`web/frame.py` run-length encodes colours and the page expands them again. If
those two ever disagree the failure is silent - a blank canvas, no error in
the console, nothing in the log - so the page's decoder is run here against a
frame the server really produced.

Node is used to run the actual shipped JavaScript rather than a Python
re-implementation of it, because a re-implementation is exactly the thing
that drifts. Skipped where node is not installed; it is not a build
dependency, only a way to test one.
"""

import json
import shutil
import subprocess

import pytest

from config import DEFAULT_CONFIG
from sim.session import Session
from web.frame import serialize

CHECK = """
import fs from "node:fs";
const src = fs.readFileSync(process.argv[2], "utf8");
const expandSrc = src.slice(src.indexOf("function expand"), src.indexOf("function layout"));
const expand = new Function(expandSrc + "; return expand;")();
const frame = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const fg = [], bg = [];
let missing = 0, glyphs = 0;
for (let y = 0; y < frame.rows; y++) {
  fg.push(expand(frame.fg[y], frame.cols));
  bg.push(expand(frame.bg[y], frame.cols));
  for (let x = 0; x < frame.cols; x++) {
    if (bg[y][x] >= 0 && !frame.palette[bg[y][x]]) missing++;
    const g = frame.glyphs[y][x];
    if (g !== " " && fg[y][x] >= 0) {
      if (!frame.palette[fg[y][x]]) missing++;
      glyphs++;
    }
  }
}
console.log(JSON.stringify({ missing, glyphs, fg, bg }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_decodes_a_frame_the_server_really_sent(tmp_path):
    session = Session(DEFAULT_CONFIG, seed=3, record_hall=False)
    session.advance(300)
    frame = serialize(session.world, session.agent, session.config, 60, 30)

    frame_file = tmp_path / "frame.json"
    frame_file.write_text(json.dumps(frame), encoding="utf-8")
    script = tmp_path / "check.mjs"
    script.write_text(CHECK, encoding="utf-8")

    done = subprocess.run(
        ["node", str(script), "web/static/app.js", str(frame_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout)
    assert result["missing"] == 0, "the page decoded a colour the palette has no entry for"
    assert result["glyphs"] > 50, "the frame the page decoded had nothing in it"

    # What the runs were meant to say, expanded here rather than by the page.
    # Comparing the two is what makes this a contract instead of a smoke test:
    # the page truncates a row to its width, so a miscounted run would decode
    # to something plausible and simply show the wrong picture.
    def intended(runs):
        out = []
        for index, count in zip(runs[0::2], runs[1::2]):
            out.extend([index] * count)
        return out

    for y in range(frame["rows"]):
        assert result["fg"][y] == intended(frame["fg"][y]), f"fg row {y} decoded wrong"
        assert result["bg"][y] == intended(frame["bg"][y]), f"bg row {y} decoded wrong"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_is_valid_javascript():
    done = subprocess.run(
        ["node", "--check", "web/static/app.js"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
