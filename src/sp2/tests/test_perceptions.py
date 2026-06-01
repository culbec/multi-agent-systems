"""Perception tests: the Environment's see: S -> P seam and the sensors."""

from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.domain.cell import Cell
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment
from src.sp2.messages.messages import AssignMessage


def test_rescue_percept_position_and_neighbors():
    env = Environment(Grid(5, 5))
    sig = Signal(1, Cell(0, 0), 0)
    agent = RescueAgent(0, Cell(2, 2), coordinator=None, peers=[])
    agent.target = Cell(0, 0)
    env.initialize([sig], Cell(2, 2), {0: Cell(2, 2)})

    percept = env.get_percept(agent, 1)
    assert percept.position == Cell(2, 2)
    assert percept.destination == Cell(0, 0)
    h_by_cell = dict(percept.neighbors)
    assert h_by_cell[Cell(1, 2)] == 3.0  # Manhattan from (1,2) to (0,0)
    assert Cell(2, 1) in h_by_cell


def test_neighbor_percept_focuses_on_assigned_target_same_tick():
    # A freshly-assigned agent (target still None) perceives its neighbourhood
    # focused on the just-received target, via intended_destination.
    env = Environment(Grid(5, 5))
    sig = Signal(1, Cell(0, 0), 0)
    agent = RescueAgent(0, Cell(2, 2), coordinator=None, peers=[])
    env.initialize([sig], Cell(2, 2), {0: Cell(2, 2)})

    agent.inbox.append(AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(0, 0)))
    percept = env.get_percept(agent, 1)
    assert percept.destination == Cell(0, 0)
    assert percept.neighbors  # not empty -- focused on the new target


def test_new_signal_perception_diff():
    env = Environment(Grid(5, 5))
    coord = CoordinatorAgent(-2, [])
    coord.initialize([])
    env.initialize([], Cell(2, 2), {})

    env.inject_signal(Signal(7, Cell(0, 0), 0))
    first = env.get_percept(coord, 1)
    assert any(s.signal_id == 7 for s in first.new_signals)

    # Already known on the next perceive.
    second = env.get_percept(coord, 2)
    assert not second.new_signals


def test_intended_destination_previews_orders():
    agent = RescueAgent(0, Cell(2, 2), coordinator=None, peers=[])
    assign = AssignMessage(sender_id=-2, receiver_id=0, tick=1, target=Cell(0, 0))
    assert agent.intended_destination((assign,), Cell(2, 2)) == Cell(0, 0)
    # No orders, no target -> head for base.
    assert agent.intended_destination((), Cell(2, 2)) == Cell(2, 2)
