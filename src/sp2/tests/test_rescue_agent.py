from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment
from src.sp2.messages.messages import AssignMessage, ClearedMessage, FreeMessage


def test_rescue_agent_single():
    # 5x5 grid, base at (2, 2), signal at (2, 4).
    grid = Grid(5, 5)
    env = Environment(grid)
    coord = CoordinatorAgent(-2, [])

    agent = RescueAgent(0, Cell(2, 2), coordinator=coord, peers=[])
    coord.rescue_agents = [agent]
    coord.agent_registry = {0: agent}

    sig = Signal(1, Cell(2, 4), 0)
    env.initialize([sig], Cell(2, 2), {0: Cell(2, 2)})
    coord.initialize([sig])

    agent.inbox.append(AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(2, 4)))

    # Tick 1: receives assignment and moves one cell toward target.
    agent.step(env, 1)
    assert env.position_of(0) == Cell(2, 3)

    # Tick 2: arrives at the signal cell.
    agent.step(env, 2)
    assert env.position_of(0) == Cell(2, 4)

    # Tick 3: clears the signal, drops target, reports free.
    agent.step(env, 3)
    assert agent.target is None
    assert env.cell_type(Cell(2, 4)) == CellType.SIGNAL_RESOLVED
    assert any(sig.location == Cell(2, 4) for sig in env.resolved_signals)

    coord_msgs = coord.drain_inbox()
    assert any(isinstance(m, ClearedMessage) and m.signal == Cell(2, 4) for m in coord_msgs)
    assert any(isinstance(m, FreeMessage) and m.agent_id == 0 for m in coord_msgs)


def test_rescue_agent_collision():
    # Two agents intend the same cell with no alternatives; lower id must yield.
    grid = Grid(5, 5)
    grid.set_cell_type(Cell(0, 0), CellType.OBSTACLE)
    grid.set_cell_type(Cell(0, 2), CellType.OBSTACLE)
    grid.set_cell_type(Cell(2, 0), CellType.OBSTACLE)

    env = Environment(grid)
    coord = CoordinatorAgent(-2, [])

    agent0 = RescueAgent(0, Cell(0, 1), coordinator=coord, peers=[])
    agent1 = RescueAgent(1, Cell(1, 0), coordinator=coord, peers=[])
    agent0.peers = [agent1]
    agent1.peers = [agent0]
    coord.rescue_agents = [agent0, agent1]
    coord.agent_registry = {0: agent0, 1: agent1}

    sig = Signal(1, Cell(1, 1), 0)
    env.initialize([sig], Cell(2, 2), {0: Cell(0, 1), 1: Cell(1, 0)})

    agent0.inbox.append(AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(1, 1)))
    agent1.inbox.append(AssignMessage(sender_id=-2, receiver_id=1, tick=1, target=Cell(1, 1)))

    # Descending id order: agent 1 reserves and moves first; agent 0 then yields.
    agent1.step(env, 1)
    agent0.step(env, 1)

    assert env.position_of(1) == Cell(1, 1)
    assert env.position_of(0) == Cell(0, 1)  # did not move
    assert agent0.wait_count == 1
