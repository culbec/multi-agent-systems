"""Action tests: each effector applies itself against the Environment and the
acting agent's own memory."""

import pytest

from src.sp2.actions.actions import (
    ClearSignalAction,
    MoveAction,
    ReportFreeAction,
    ReserveAction,
    UpdateHeuristicAction,
    WaitAction,
)
from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment
from src.sp2.messages.messages import ClearedMessage, FreeMessage


def test_move_action_updates_world_and_agent_memory():
    env = Environment(Grid(5, 5))
    agent = RescueAgent(0, Cell(2, 2), coordinator=None, peers=[])
    env.initialize([], Cell(2, 2), {0: Cell(2, 2)})

    MoveAction(Cell(2, 2), Cell(2, 3), new_h=1.0).execute(env, agent, 1)

    assert env.position_of(0) == Cell(2, 3)  # world
    assert agent.current_h == 1.0  # memory
    assert agent.movement_history[-1] == Cell(2, 3)  # memory


def test_update_heuristic_action_rejects_decrease():
    env = Environment(Grid(3, 3))
    agent = RescueAgent(0, Cell(0, 0), coordinator=None, peers=[])
    env.initialize([], Cell(0, 0), {0: Cell(0, 0)})
    target = Cell(2, 2)

    UpdateHeuristicAction(Cell(0, 0), target, 5.0).execute(env, agent, 1)
    assert env.heuristic(Cell(0, 0), target) == 5.0
    assert agent.current_h == 5.0

    with pytest.raises(AssertionError):
        UpdateHeuristicAction(Cell(0, 0), target, 1.0).execute(env, agent, 1)


def test_reserve_action_claims_cell():
    env = Environment(Grid(3, 3))
    agent = RescueAgent(0, Cell(0, 0), coordinator=None, peers=[])
    ReserveAction(Cell(1, 1), tick=4).execute(env, agent, 4)
    assert Cell(1, 1) in env.reservations(4)


def test_clear_signal_action_resolves_and_announces():
    env = Environment(Grid(3, 3))
    coord = CoordinatorAgent(-2, [])
    agent = RescueAgent(0, Cell(1, 1), coordinator=coord, peers=[])
    env.initialize([Signal(1, Cell(1, 1), 0)], Cell(0, 0), {0: Cell(1, 1)})

    ClearSignalAction(Cell(1, 1), tick=2).execute(env, agent, 2)

    assert env.cell_type(Cell(1, 1)) == CellType.SIGNAL_RESOLVED
    assert any(s.location == Cell(1, 1) for s in env.resolved_signals)
    assert any(isinstance(m, ClearedMessage) for m in coord.drain_inbox())


def test_report_free_action_sends_free_and_sets_flag():
    coord = CoordinatorAgent(-2, [])
    agent = RescueAgent(0, Cell(2, 2), coordinator=coord, peers=[])
    ReportFreeAction(Cell(2, 2)).execute(env=None, agent=agent, tick=1)
    assert agent.free_sent is True
    assert any(isinstance(m, FreeMessage) for m in coord.drain_inbox())


def test_wait_action_increments_counter():
    agent = RescueAgent(0, Cell(2, 2), coordinator=None, peers=[])
    WaitAction().execute(env=None, agent=agent, tick=1)
    assert agent.wait_count == 1
