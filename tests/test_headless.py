"""The layering guarantee: the sim runs without a graphics library.

Checked in a fresh interpreter rather than in this one. `sys.modules` is
global, so asserting pygame is absent here only holds while no other test has
imported it - and the moment one does (render.screen, say) this test starts
failing for a reason that has nothing to do with the property it protects.
A subprocess imports exactly the headless modules and nothing else.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HEADLESS_MODULES = (
    "agent.fov",
    "agent.goals",
    "agent.loadout",
    "agent.memory",
    "agent.pathing",
    "agent.stats",
    "agent.threat",
    "config",
    "render.flourish",
    "render.fog",
    "render.hud",
    "render.menu",
    "render.overlays",
    "render.palette",
    "sim.ai",
    "sim.chronicle",
    "sim.combat",
    "sim.harness",
    "sim.items",
    "sim.monsters",
    "sim.perks",
    "sim.tick",
    "world.chunks",
    "world.gen_bsp",
    "world.gen_cave",
    "world.gen_cavern",
    "world.populate",
    "world.tiles",
)

_PROBE = """
import importlib, sys
for name in {modules!r}:
    importlib.import_module(name)
print("ANSWER:" + str("pygame" in sys.modules))
"""


def _answer(stdout: str) -> str:
    """Pull the probe's answer out of its output.

    Tagged rather than read as the whole of stdout, because importing pygame
    prints a banner to stdout - so the naive read returns the banner and the
    answer together, and the check quietly compares the wrong string.
    """
    for line in stdout.splitlines():
        if line.startswith("ANSWER:"):
            return line[len("ANSWER:") :].strip()
    return stdout.strip()


def test_headless_modules_do_not_import_pygame():
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(modules=list(HEADLESS_MODULES))],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert _answer(result.stdout) == "False", (
        "one of the headless modules pulled in pygame:\n" + result.stdout
    )


def test_the_headless_modules_actually_exist():
    """A typo in the list above would make the check pass by importing nothing."""
    import importlib

    for name in HEADLESS_MODULES:
        assert importlib.import_module(name) is not None


def test_the_probe_would_notice_pygame():
    """The guard has to be able to fail, or it guards nothing."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(modules=["render.screen"])],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert _answer(result.stdout) == "True", "render.screen does import pygame"
