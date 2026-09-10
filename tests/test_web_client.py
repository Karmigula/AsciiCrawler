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


FIT = """
import fs from "node:fs";
const src = fs.readFileSync(process.argv[2], "utf8");
const body = src.slice(src.indexOf("const CELL_RATIO"), src.indexOf("if (typeof module"));
const fitCells = new Function(body + "; return fitCells;")();
const cases = JSON.parse(process.argv[3]);
console.log(JSON.stringify(cases.map(([w, h, cols, rows]) => fitCells(w, h, cols, rows))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_grid_is_scaled_to_fit_the_window_it_is_drawn_in(tmp_path):
    """The page sized cells off the width alone and ran off the bottom.

    On a wide window that is not a small error: at 104 columns the grid came
    out around three quarters as tall as it was wide, so a maximised browser
    showed the top two thirds of the map and scrolled for the rest. Both axes
    have to be considered, and the smaller one has to win.
    """
    cases = [
        (1712, 760, 104, 36),  # the window this was reported from
        (1560, 880, 104, 36),  # 1080p, maximised
        (2200, 1250, 104, 36),  # 1440p
        (3000, 700, 104, 36),  # ultrawide and short
        (900, 480, 104, 36),  # a small laptop
        (600, 1000, 104, 36),  # narrow and tall
        (380, 500, 104, 36),  # a phone
        (200, 200, 104, 36),  # absurd, but it must not crash or go negative
    ]
    script = tmp_path / "fit.mjs"
    script.write_text(FIT, encoding="utf-8")

    done = subprocess.run(
        ["node", str(script), "web/static/app.js", json.dumps(cases)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    sizes = json.loads(done.stdout)

    for (avail_w, avail_h, cols, rows), size in zip(cases, sizes):
        width = size["cellW"] * cols
        height = size["cellH"] * rows
        assert size["cellW"] >= 3, "cells must stay big enough to see"
        if avail_w >= 380 and avail_h >= 300:
            assert width <= avail_w, f"{width}px of grid in {avail_w}px of window"
            assert height <= avail_h, f"{height}px of grid in {avail_h}px of window"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_a_wider_window_gets_bigger_cells_not_a_cropped_map(tmp_path):
    """Growing the window must scale the same grid up, never show more of it.

    Everyone watches one shared frame, so the number of cells is fixed by the
    server; the page's only move is to draw them larger.
    """
    script = tmp_path / "fit.mjs"
    script.write_text(FIT, encoding="utf-8")
    cases = [(800, 500, 104, 36), (1600, 1000, 104, 36)]

    done = subprocess.run(
        ["node", str(script), "web/static/app.js", json.dumps(cases)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    small, large = json.loads(done.stdout)

    assert large["cellW"] > small["cellW"]
    assert large["cellH"] > small["cellH"]
