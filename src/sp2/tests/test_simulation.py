from src.sp2.config import SimulationConfig
from src.sp2.simulation import Simulation


def test_simulation_smoke():
    # Smoke test: 5x5 grid, 1 agent, 1 signal, no obstacles.
    # Base at (2, 2). Signal at (0, 0).
    # Manhattan distance = abs(2-0) + abs(2-0) = 4.
    config = SimulationConfig(
        rows=5,
        cols=5,
        obstacle_coords=[],
        base_location=(2, 2),
        initial_signals=[(0, 0)],
        agent_count=1,
        dynamic_signal_stream=[],
        max_ticks=100,
    )

    sim = Simulation(config)
    stats = sim.run()

    assert stats["signals_resolved"] == 1
    # LRTA* with 1 agent on empty grid should follow shortest path perfectly
    # Starting clean at tick 1 means communication starts on tick 1, and agent starts moving on tick 2.
    # It takes 4 moves to reach, so it reaches and clears on tick 6 (sub-phase A)
    assert stats["makespan"] == 6
    assert stats["total_steps"] == 4


def test_simulation_multi_agent():
    # Multi-agent: 10x10 grid, 3 agents, 5 signals, obstacles.
    config = SimulationConfig(
        rows=10,
        cols=10,
        obstacle_coords=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)],
        base_location=(0, 0),
        initial_signals=[(9, 9), (0, 9), (9, 0), (5, 9), (9, 5)],
        agent_count=3,
        dynamic_signal_stream=[],
        max_ticks=200,
    )

    sim = Simulation(config)
    stats = sim.run()

    assert stats["signals_resolved"] == 5
    assert stats["makespan"] > 0

    # Let's validate from frames that no two agents occupy the same cell at the same tick (except at the base cell)
    for frame in sim.frames:
        agent_positions = [
            agent["position"]
            for agent in frame["agents"]
            if agent["state"] != "halted" and agent["position"] != config.base_location
        ]
        # Ensure no duplicates
        assert len(agent_positions) == len(set(agent_positions))


def test_simulation_dynamic_signals():
    # Dynamic signals: 8x8 grid, 2 agents, 1 initial signal, 2 dynamic signals at ticks 10 and 20.
    config = SimulationConfig(
        rows=8,
        cols=8,
        obstacle_coords=[],
        base_location=(4, 4),
        initial_signals=[(0, 0)],
        agent_count=2,
        dynamic_signal_stream=[
            (0, 7, 5),  # row, col, tick
            (7, 0, 10),
        ],
        max_ticks=150,
    )

    sim = Simulation(config)
    stats = sim.run()

    assert stats["signals_resolved"] == 3


def test_simulation_max_ticks_safety():
    # Max ticks safety: 5x5 grid with unreachable signal (surrounded by obstacles)
    config = SimulationConfig(
        rows=5,
        cols=5,
        # Surround (0, 0) with obstacles
        obstacle_coords=[(0, 1), (1, 0), (1, 1)],
        base_location=(4, 4),
        initial_signals=[(0, 0)],
        agent_count=1,
        dynamic_signal_stream=[],
        max_ticks=20,
    )

    sim = Simulation(config)
    stats = sim.run()

    assert stats["signals_resolved"] == 0
    assert stats["total_ticks"] == 20
    assert sim.terminated
