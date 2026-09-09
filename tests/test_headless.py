import sys


def test_headless_modules_do_not_import_pygame():
    import config
    import sim.tick
    import world.hardcoded

    assert config.DEFAULT_CONFIG is not None
    assert sim.tick.tick is not None
    assert world.hardcoded.build_map is not None
    assert "pygame" not in sys.modules
