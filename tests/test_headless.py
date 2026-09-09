import sys


def test_headless_modules_do_not_import_pygame():
    import agent.fov
    import agent.goals
    import agent.memory
    import agent.pathing
    import config
    import render.fog
    import sim.harness
    import sim.tick
    import world.chunks
    import world.gen_bsp
    import world.gen_cave
    import world.gen_cavern
    import world.tiles

    assert config.DEFAULT_CONFIG is not None
    assert sim.tick.tick is not None
    assert world.tiles.Tile is not None
    assert world.gen_bsp.generate is not None
    assert world.gen_cave.generate is not None
    assert world.gen_cavern.generate is not None
    assert world.chunks.ChunkStore is not None
    assert agent.fov.compute_fov is not None
    assert agent.memory.Memory is not None
    assert agent.pathing.astar is not None
    assert agent.goals.ExploreGoal is not None
    assert sim.harness.run_ticks is not None
    assert render.fog.fog_grid is not None
    assert "pygame" not in sys.modules
