from src.sp2.agents.agent import Agent
from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.environment_agent import EnvironmentAgent
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    HUpdateMessage,
    MoveMessage,
    NeighborQueryMessage,
    NewSignalMessage,
    TerminateMessage,
)


class MockAgent(Agent):
    def step(self, tick: int) -> None:
        pass


def test_environment_agent():
    grid = Grid(5, 5)
    mock_coordinator = MockAgent(-2)
    env = EnvironmentAgent(-1, grid, mock_coordinator)

    # 2 signals
    sig1 = Signal(1, Cell(0, 0), 0)
    sig2 = Signal(2, Cell(4, 4), 0)

    # 1 rescue agent starting at (2, 2)
    rescue_agent = MockAgent(0)
    env.register_rescue_agents([rescue_agent])

    env.initialize([sig1, sig2], Cell(2, 2), {0: Cell(2, 2)})

    # Verify h-table initialization for target sig1
    assert env.heuristic_table[(Cell(0, 0), sig1.location)] == 0.0
    assert env.heuristic_table[(Cell(4, 4), sig1.location)] == 8.0
    assert env.heuristic_table[(Cell(1, 0), sig1.location)] == 1.0
    assert env.heuristic_table[(Cell(2, 2), sig1.location)] == 4.0

    # Test NeighborQueryMessage with target sig1
    query = NeighborQueryMessage(sender_id=0, receiver_id=-1, tick=1, position=Cell(2, 2), target=sig1.location)
    env.send_message(env, query)
    env.step(1)

    msgs = rescue_agent.drain_inbox()
    assert len(msgs) == 1
    resp = msgs[0]
    assert resp.msg_type == "NEIGHBOR_RESPONSE"
    assert len(resp.neighbors) == 4
    # Check that h-value for neighbor (1, 2) is 3.0 (Manhattan distance to sig1 at (0, 0))
    for neighbor, c_type, h_val in resp.neighbors:
        if neighbor == Cell(1, 2):
            assert h_val == 3.0

    # Test MoveMessage
    move = MoveMessage(sender_id=0, receiver_id=-1, tick=2, from_cell=Cell(2, 2), to_cell=Cell(2, 3))
    env.send_message(env, move)
    env.step(2)

    assert env.occupancy_map[Cell(2, 3)] == 0
    assert Cell(2, 2) not in env.occupancy_map
    assert grid.get_cell_type(Cell(2, 3)) == CellType.AGENT
    assert grid.get_cell_type(Cell(2, 2)) == CellType.BASE

    # Test HUpdateMessage with target sig1
    h_up = HUpdateMessage(sender_id=0, receiver_id=-1, tick=3, cell=Cell(2, 3), value=10.0, target=sig1.location)
    env.send_message(env, h_up)
    env.step(3)

    assert env.heuristic_table[(Cell(2, 3), sig1.location)] == 10.0


def test_coordinator_agent():
    agent0 = MockAgent(0)
    agent1 = MockAgent(1)

    coord = CoordinatorAgent(-2, [agent0, agent1])

    # Initialize with 3 signals
    sig1 = Signal(1, Cell(0, 1), 0)
    sig2 = Signal(2, Cell(4, 4), 0)
    sig3 = Signal(3, Cell(0, 4), 0)

    coord.initialize([sig1, sig2, sig3])

    # 1. Send FreeMessage from agent 0 at position (0,0)
    free_msg = FreeMessage(sender_id=0, receiver_id=-2, tick=1, agent_id=0, position=Cell(0, 0))
    coord.send_message(coord, free_msg)
    coord.step(1)

    # Verify agent 0 got ASSIGN with sig1 (nearest to (0,0) is (0,1) with dist 1, vs (0,4) with dist 4)
    msgs0 = agent0.drain_inbox()
    assert len(msgs0) == 1
    assert isinstance(msgs0[0], AssignMessage)
    assert msgs0[0].target == Cell(0, 1)
    assert coord.assignments[0] == sig1
    assert sig1 not in coord.pending_signals

    # 2. Send ClearedMessage for sig2 (which is in pending_signals)
    cleared_msg = ClearedMessage(sender_id=0, receiver_id=-2, tick=2, signal=Cell(4, 4))
    coord.send_message(coord, cleared_msg)
    coord.step(2)

    # Verify sig2 is removed from pending_signals
    assert all(sig.signal_id != 2 for sig in coord.pending_signals)

    # 3. Dynamic NewSignalMessage with idle agent
    # First, let's put agent 1 in idle_agents by sending FreeMessage with no pending signals (wait, sig3 is still pending! So agent 1 will get assigned to sig3)
    free_msg1 = FreeMessage(sender_id=1, receiver_id=-2, tick=3, agent_id=1, position=Cell(0, 3))
    coord.send_message(coord, free_msg1)
    coord.step(3)

    # Agent 1 should get assigned to sig3
    msgs1 = agent1.drain_inbox()
    assert len(msgs1) == 1
    assert msgs1[0].target == Cell(0, 4)
    assert coord.assignments[1] == sig3
    assert not coord.pending_signals

    # Now both agents are assigned. If agent 0 clears its signal and has no more signals, it becomes idle
    cleared_msg0 = ClearedMessage(sender_id=0, receiver_id=-2, tick=4, signal=Cell(0, 1))
    free_msg0_idle = FreeMessage(sender_id=0, receiver_id=-2, tick=4, agent_id=0, position=Cell(0, 1))
    coord.send_message(coord, cleared_msg0)
    coord.send_message(coord, free_msg0_idle)
    coord.step(4)

    # No pending signals left, so agent 0 should be in idle_agents
    assert 0 in coord.idle_agents
    assert coord.idle_agents[0] == Cell(0, 1)

    # Now send NewSignalMessage at Cell(0, 2)
    new_sig_msg = NewSignalMessage(sender_id=-1, receiver_id=-2, tick=5, location=Cell(0, 2))
    coord.send_message(coord, new_sig_msg)
    coord.step(5)

    # Agent 0 was idle, so it should be immediately assigned
    assert 0 not in coord.idle_agents
    msgs0_new = agent0.drain_inbox()
    assert len(msgs0_new) == 1
    assert msgs0_new[0].target == Cell(0, 2)

    # 4. Termination check
    # Clear both assignments and make both idle
    # Agent 0 clears (0, 2)
    coord.send_message(coord, ClearedMessage(sender_id=0, receiver_id=-2, tick=6, signal=Cell(0, 2)))
    coord.send_message(coord, FreeMessage(sender_id=0, receiver_id=-2, tick=6, agent_id=0, position=Cell(0, 2)))
    # Agent 1 clears (0, 4)
    coord.send_message(coord, ClearedMessage(sender_id=1, receiver_id=-2, tick=6, signal=Cell(0, 4)))
    coord.send_message(coord, FreeMessage(sender_id=1, receiver_id=-2, tick=6, agent_id=1, position=Cell(0, 4)))
    coord.step(6)

    # Both should get TerminateMessage
    term_msgs0 = agent0.drain_inbox()
    assert len(term_msgs0) == 1
    assert isinstance(term_msgs0[0], TerminateMessage)

    term_msgs1 = agent1.drain_inbox()
    assert len(term_msgs1) == 1
    assert isinstance(term_msgs1[0], TerminateMessage)
