from src.sp2.domain.cell import Cell
from src.sp2.domain.signal import Signal
from src.sp2.utils.stats import compute_statistics


class DummyAgent:
    def __init__(self, agent_id, movement_history):
        self.agent_id = agent_id
        self.movement_history = movement_history


def test_compute_statistics():
    # Build dummy frames
    # Each frame has 'agents' and 'heuristic_map'
    frames = [
        {
            "agents": [{"id": 0, "state": "idle", "target": None}, {"id": 1, "state": "idle", "target": None}],
            "heuristic_map": {(0, 0): 5.0, (1, 1): 2.0},
        },
        {
            "agents": [
                {"id": 0, "state": "moving", "target": (0, 0)},
                {"id": 1, "state": "waiting", "target": (1, 1)},
            ],
            "heuristic_map": {(0, 0): 4.0, (1, 1): 2.0},
        },
        {
            "agents": [{"id": 0, "state": "moving", "target": (0, 0)}, {"id": 1, "state": "moving", "target": (1, 1)}],
            "heuristic_map": {(0, 0): 3.0, (1, 1): 1.0},
        },
    ]

    # Dummy resolved signals
    sig1 = Signal(1, Cell(0, 0), 1, resolved_at_tick=2, resolved_by=0)
    sig2 = Signal(2, Cell(1, 1), 1, resolved_at_tick=3, resolved_by=1)
    resolved_signals = [sig1, sig2]

    # Dummy rescue agents
    agents = [DummyAgent(0, [Cell(2, 2), Cell(1, 1), Cell(0, 0)]), DummyAgent(1, [Cell(3, 3), Cell(3, 3), Cell(1, 1)])]

    stats = compute_statistics(frames, resolved_signals, agents, 3)

    assert stats["makespan"] == 3
    assert stats["total_steps"] == 4
    assert stats["total_ticks"] == 3
    assert stats["signals_resolved"] == 2
    assert stats["avg_resolution_time"] == 1.5  # ((2-1) + (3-1)) / 2 = 1.5

    # Check per-agent statistics
    per_agent_0 = next(a for a in stats["per_agent"] if a["id"] == 0)
    per_agent_1 = next(a for a in stats["per_agent"] if a["id"] == 1)

    assert per_agent_0["steps"] == 2
    assert per_agent_0["signals_resolved"] == 1
    assert per_agent_0["idle_ticks"] == 1
    assert per_agent_0["wait_ticks"] == 0
    assert per_agent_0["idle_ratio"] == 1.0 / 3.0

    assert per_agent_1["steps"] == 2
    assert per_agent_1["signals_resolved"] == 1
    assert per_agent_1["idle_ticks"] == 1
    assert per_agent_1["wait_ticks"] == 1
    assert per_agent_1["idle_ratio"] == 1.0 / 3.0

    # Check heuristic convergence
    # Between frame 0 and 1: (0,0) diff is |4-5| = 1.0, (1,1) diff is |2-2| = 0.0. Mean is 0.5
    # Between frame 1 and 2: (0,0) diff is |3-4| = 1.0, (1,1) diff is |1-2| = 1.0. Mean is 1.0
    # Average change: (0.5 + 1.0) / 2 = 0.75
    assert abs(stats["mean_heuristic_change"] - 0.75) < 1e-6
