from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.environment_agent import EnvironmentAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import AssignMessage, ClearedMessage, FreeMessage


def test_rescue_agent_single():
    # 5x5 grid, base at (2, 2)
    grid = Grid(5, 5)
    mock_coord = CoordinatorAgent(-2, [])
    env = EnvironmentAgent(-1, grid, mock_coord)

    sig = Signal(1, Cell(2, 4), 0)

    agent = RescueAgent(0, Cell(2, 2), env, mock_coord, [])
    mock_coord.rescue_agents = [agent]
    mock_coord.agent_registry = {0: agent}
    env.register_rescue_agents([agent])

    env.initialize([sig], Cell(2, 2), {0: Cell(2, 2)})
    mock_coord.initialize([sig])

    assign_msg = AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(2, 4))
    agent.send_message(agent, assign_msg)

    # Tick 1
    agent.step(1)
    env.step(1)
    agent.step_act(1)

    assert agent.position == Cell(2, 3)

    # Tick 2
    agent.step(2)
    env.step(2)
    agent.step_act(2)

    assert agent.position == Cell(2, 4)

    # Tick 3
    agent.step(3)

    env_msgs = env.drain_inbox()
    assert any(isinstance(m, ClearedMessage) and m.signal == Cell(2, 4) for m in env_msgs)

    coord_msgs = mock_coord.drain_inbox()
    assert any(isinstance(m, FreeMessage) and m.agent_id == 0 for m in coord_msgs)

    assert agent.target is None


def test_rescue_agent_collision():
    # Two agents intending to move to the same cell, and no other cells are available.
    # Verify lower-id waits, higher proceeds.
    grid = Grid(5, 5)

    # Set obstacles to block other neighbors
    # Cell(0,1) neighbors are (0,0), (0,2), (1,1). We make (0,0) and (0,2) obstacles.
    # Cell(1,0) neighbors are (0,0), (2,0), (1,1). We make (0,0) and (2,0) obstacles.
    grid.set_cell_type(Cell(0, 0), CellType.OBSTACLE)
    grid.set_cell_type(Cell(0, 2), CellType.OBSTACLE)
    grid.set_cell_type(Cell(2, 0), CellType.OBSTACLE)

    mock_coord = CoordinatorAgent(-2, [])
    env = EnvironmentAgent(-1, grid, mock_coord)

    # 2 agents, agent 0 and agent 1
    # They start at (0, 1) and (1, 0)
    # Their target is (1, 1).
    agent0 = RescueAgent(0, Cell(0, 1), env, mock_coord, [])
    agent1 = RescueAgent(1, Cell(1, 0), env, mock_coord, [])

    agent0.peers = [agent1]
    agent1.peers = [agent0]

    mock_coord.rescue_agents = [agent0, agent1]
    mock_coord.agent_registry = {0: agent0, 1: agent1}
    env.register_rescue_agents([agent0, agent1])

    sig = Signal(1, Cell(1, 1), 0)
    env.initialize([sig], Cell(2, 2), {0: Cell(0, 1), 1: Cell(1, 0)})

    # Re-apply obstacles because initialize overwrites them with FREE unless specified!
    # Wait, initialize only sets BASE, SIGNAL, AGENT and leaves obstacles.
    # But let's make sure grid still has obstacles
    grid.set_cell_type(Cell(0, 0), CellType.OBSTACLE)
    grid.set_cell_type(Cell(0, 2), CellType.OBSTACLE)
    grid.set_cell_type(Cell(2, 0), CellType.OBSTACLE)

    mock_coord.initialize([sig])

    # Assign targets
    agent0.send_message(agent0, AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(1, 1)))
    agent1.send_message(agent1, AssignMessage(sender_id=-2, receiver_id=1, tick=1, target=Cell(1, 1)))

    # Sub-phase A
    agent0.step(1)
    agent1.step(1)

    # Environment processes queries
    env.step(1)

    # Sub-phase B
    # Run in descending order of agent_id
    agent1.step_act(1)  # agent 1 selects (1,1), reserves it, moves to (1,1)
    agent0.step_act(1)  # agent 0 selects (1,1), sees reservation, yields (waits)

    assert agent1.position == Cell(1, 1)
    assert agent0.position == Cell(0, 1)  # should not have moved!
    assert agent0.wait_count == 1
