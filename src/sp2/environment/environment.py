from typing import TYPE_CHECKING

from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.reservation import Reservation
from src.sp2.domain.signal import Signal
from src.sp2.environment.state import State
from src.sp2.perceptions.percepts import CoordinatorPercept, RescuePercept
from src.sp2.perceptions.sensors import (
    InboxSensor,
    NeighborSensor,
    NewSignalSensor,
    ReservationSensor,
)

if TYPE_CHECKING:  # pragma: no cover
    from src.sp2.actions.action import Action
    from src.sp2.agents.agent import Agent
    from src.sp2.perceptions.percept import Percept

# Tolerance for the h-monotonicity tripwire (guards against float noise).
_H_EPSILON = 1e-9


class Environment:
    """The state authority and the two seams of the agent loop.

    Owns the world :class:`State` and is the only place world invariants are
    enforced (single-occupancy, h-monotonicity, signal lifecycle). It is **not**
    an ``Agent``: it has no inbox, no ``step``, and sends no messages.

    Two seams sit here, mirroring the AIMA framework:

    * ``get_percept`` -- the ``see: S -> P`` function. Builds the percept for an
      agent by composing sensor objects (control inverted into the Environment).
    * ``update_state`` -- the ``env: S x A -> S`` function. Applies an agent's
      chosen actions; each ``Action`` mutates the world only through the guarded
      primitives below.
    """

    def __init__(self, grid: Grid):
        self.state = State(grid=grid)
        # Sensors compose each agent's percept. Stateless; reused every tick.
        self._neighbor_sensor = NeighborSensor()
        self._reservation_sensor = ReservationSensor()
        self._inbox_sensor = InboxSensor()
        self._new_signal_sensor = NewSignalSensor()

    # Convenience views onto the State (kept so existing readers -- frame
    # collection, stats, main.py -- keep working against the Environment)
    @property
    def grid(self) -> Grid:
        return self.state.grid

    @property
    def base(self) -> Cell | None:
        return self.state.base

    @property
    def heuristic_table(self) -> dict[tuple[Cell, Cell], float]:
        return self.state.heuristic_table

    @property
    def active_signals(self) -> dict[int, Signal]:
        return self.state.active_signals

    @property
    def resolved_signals(self) -> list[Signal]:
        return self.state.resolved_signals

    # Initialization (ported verbatim from EnvironmentAgent.initialize)
    def initialize(self, signals: list[Signal], base: Cell, rescue_agent_positions: dict[int, Cell]) -> None:
        s = self.state
        s.base = base

        # 1. Cell types in the grid
        s.grid.set_cell_type(base, CellType.BASE)
        for sig in signals:
            s.grid.set_cell_type(sig.location, CellType.SIGNAL)
        for _, pos in rescue_agent_positions.items():
            if pos != base:
                s.grid.set_cell_type(pos, CellType.AGENT)

        # 2. Heuristic table with (cell, target) keys
        s.heuristic_table.clear()
        for cell in s.grid.all_cells():
            if s.grid.get_cell_type(cell) == CellType.OBSTACLE:
                continue
            for sig in signals:
                s.heuristic_table[(cell, sig.location)] = float(cell.manhattan_distance(sig.location))
            s.heuristic_table[(cell, base)] = float(cell.manhattan_distance(base))

        # 3. Authoritative positions, signals, reservations
        s.positions = dict(rescue_agent_positions)
        s.active_signals = {sig.signal_id: sig for sig in signals}
        s.resolved_signals = []
        s.reservations = {}

    # Accessors (read-only; used by the sensors)
    def passable_neighbors(self, cell: Cell) -> list[Cell]:
        return self.state.grid.get_passable_neighbors(cell)

    def cell_type(self, cell: Cell) -> CellType:
        return self.state.grid.get_cell_type(cell)

    def heuristic(self, cell: Cell, target: Cell) -> float:
        return self.state.heuristic_table.get((cell, target), float(cell.manhattan_distance(target)))

    def active_signals_view(self) -> dict[int, Signal]:
        return dict(self.state.active_signals)

    def occupant(self, cell: Cell) -> int | None:
        return self.state.occupant(cell)

    def position_of(self, agent_id: int) -> Cell | None:
        return self.state.position_of(agent_id)

    def reservations(self, tick: int) -> set[Cell]:
        return {res.cell for res in self.state.reservations.get(tick, set())}

    # see: S -> P
    def get_percept(self, agent: "Agent", tick: int) -> "Percept":
        """Build the percept for ``agent`` from the world State and its vantage."""
        if type(agent).__name__ == "CoordinatorAgent":
            return CoordinatorPercept(
                new_signals=self._new_signal_sensor.sense(self, agent, tick),
                messages=self._inbox_sensor.sense(self, agent, tick),
            )

        # Rescue agent. Drain the inbox first so the neighborhood can be focused
        # on the destination implied by any orders received this tick
        messages = self._inbox_sensor.sense(self, agent, tick)
        destination = agent.intended_destination(messages, self.base)
        position = self.position_of(agent.agent_id)
        position_h = (
            self.heuristic(position, destination)
            if position is not None and destination is not None and position != destination
            else None
        )
        neighbors = self._neighbor_sensor.sense(self, agent, tick, destination=destination)
        reserved = self._reservation_sensor.sense(self, agent, tick)
        return RescuePercept(
            position=position,
            destination=destination,
            position_h=position_h,
            neighbors=neighbors,
            reserved_cells=reserved,
            messages=messages,
        )

    # env: S x A -> S
    def update_state(self, agent: "Agent", actions: "list[Action]", tick: int) -> None:
        """Apply an agent's chosen actions. There is no dispatcher -- each
        action applies itself through the guarded primitives below."""
        for action in actions:
            action.execute(self, agent, tick)

    # Guarded mutators (called by Action objects; enforce the invariants)
    def move(self, agent_id: int, from_cell: Cell, to_cell: Cell) -> None:
        s = self.state
        # Single-occupancy tripwire. The base may legitimately hold several
        # idle agents, so it is exempt.
        occupant = s.occupant(to_cell)
        assert to_cell == s.base or occupant is None or occupant == agent_id, (
            f"single-occupancy violated: agent {agent_id} -> {to_cell} held by agent {occupant}"
        )

        s.positions[agent_id] = to_cell

        # Restore the vacated cell's type, then mark the destination occupied
        # (ported from the old MoveMessage branch)
        if from_cell == s.base:
            s.grid.set_cell_type(from_cell, CellType.BASE)
        elif any(sig.location == from_cell for sig in s.active_signals.values()):
            s.grid.set_cell_type(from_cell, CellType.SIGNAL)
        else:
            s.grid.set_cell_type(from_cell, CellType.FREE)
        s.grid.set_cell_type(to_cell, CellType.AGENT)

    def update_heuristic(self, cell: Cell, target: Cell, value: float) -> None:
        s = self.state
        current = s.heuristic_table.get((cell, target), float(cell.manhattan_distance(target)))
        # h-monotonicity tripwire: LRTA* never decreases a learned estimate
        assert value >= current - _H_EPSILON, (
            f"h-monotonicity violated at {cell}->{target}: {value} < {current}"
        )
        s.heuristic_table[(cell, target)] = value

    def resolve_signal(self, signal_cell: Cell, agent_id: int, tick: int) -> Signal | None:
        s = self.state
        resolved: Signal | None = None
        for signal_id, sig in list(s.active_signals.items()):
            if sig.location == signal_cell:
                sig.resolved_at_tick = tick
                sig.resolved_by = agent_id
                s.resolved_signals.append(sig)
                del s.active_signals[signal_id]
                resolved = sig
        s.grid.set_cell_type(signal_cell, CellType.FREE)
        return resolved

    def reserve(self, agent_id: int, cell: Cell, tick: int) -> None:
        self.state.reservations.setdefault(tick, set()).add(Reservation(agent_id=agent_id, cell=cell, tick=tick))

    def clear_reservations(self, tick: int) -> None:
        self.state.reservations.pop(tick, None)

    def inject_signal(self, signal: Signal) -> None:
        """Add a dynamically-appearing signal to the world (Decision D2: no
        message - the coordinator's NewSignalSensor diffs it next perceive)."""
        s = self.state
        s.grid.set_cell_type(signal.location, CellType.SIGNAL)
        s.active_signals[signal.signal_id] = signal
        for cell in s.grid.all_cells():
            if s.grid.get_cell_type(cell) == CellType.OBSTACLE:
                continue
            s.heuristic_table[(cell, signal.location)] = float(cell.manhattan_distance(signal.location))