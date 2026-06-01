"""Coordinator tests, driven through perception (percepts) and the step loop --
no NEW_SIGNAL message any more (Decision D2)."""

from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.domain.cell import Cell
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment
from src.sp2.messages.messages import AssignMessage, ClearedMessage, FreeMessage, TerminateMessage


def _wire(initial_signals, agent_positions):
    env = Environment(Grid(5, 5))
    agents = [RescueAgent(aid, pos, coordinator=None, peers=[]) for aid, pos in agent_positions.items()]
    coord = CoordinatorAgent(-2, agents)
    for a in agents:
        a.coordinator = coord
    env.initialize(initial_signals, Cell(2, 2), agent_positions)
    coord.initialize(initial_signals)
    coord.no_more_dynamic_signals = True
    return env, coord, {a.agent_id: a for a in agents}


def test_free_message_triggers_nearest_assignment():
    sig1 = Signal(1, Cell(0, 1), 0)
    sig2 = Signal(2, Cell(4, 4), 0)
    sig3 = Signal(3, Cell(0, 4), 0)
    env, coord, agents = _wire([sig1, sig2, sig3], {0: Cell(2, 2), 1: Cell(2, 2)})

    # Agent 0 reports free from (0,0): nearest pending is sig1 at (0,1).
    coord.inbox.append(FreeMessage(sender_id=0, receiver_id=-2, tick=1, agent_id=0, position=Cell(0, 0)))
    coord.step(env, 1)

    msgs0 = agents[0].drain_inbox()
    assert any(isinstance(m, AssignMessage) and m.target == Cell(0, 1) for m in msgs0)
    assert coord.assignments[0] == sig1
    assert sig1 not in coord.pending_signals


def test_injected_signal_perceived_and_assigned_to_idle():
    env, coord, agents = _wire([], {0: Cell(2, 2), 1: Cell(2, 2)})
    coord.idle_agents[0] = Cell(2, 2)

    env.inject_signal(Signal(7, Cell(0, 0), 3))
    coord.step(env, 3)

    msgs0 = agents[0].drain_inbox()
    assert any(isinstance(m, AssignMessage) and m.target == Cell(0, 0) for m in msgs0)
    assert 0 not in coord.idle_agents
    # Perceived once; not re-flagged on the next perceive.
    assert 7 in coord.known_signal_ids


def test_retire_cleared_removes_pending_and_assignment():
    sig1 = Signal(1, Cell(0, 1), 0)
    sig2 = Signal(2, Cell(4, 4), 0)
    env, coord, agents = _wire([sig1, sig2], {0: Cell(2, 2)})
    coord.assignments[0] = sig1
    coord.pending_signals = [sig2]

    coord.inbox.append(ClearedMessage(sender_id=0, receiver_id=-2, tick=2, signal=Cell(0, 1)))
    coord.step(env, 2)

    assert 0 not in coord.assignments
    assert all(s.signal_id != 1 for s in coord.pending_signals)


def test_termination_when_all_idle_and_no_work():
    env, coord, agents = _wire([], {0: Cell(2, 2), 1: Cell(2, 2)})
    coord.idle_agents = {0: Cell(2, 2), 1: Cell(2, 2)}

    coord.step(env, 5)

    for aid in (0, 1):
        msgs = agents[aid].drain_inbox()
        assert any(isinstance(m, TerminateMessage) for m in msgs)
