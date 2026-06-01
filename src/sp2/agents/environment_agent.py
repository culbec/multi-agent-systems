"""DEPRECATED -- pre-PAGE design.

``EnvironmentAgent`` modeled the environment as a third message-passing agent.
The PAGE refactor replaced it with :class:`src.sp2.environment.Environment` (a
non-agent state authority). This module is retained only as a reference and is
**not** wired into the live system: it is not exported from ``agents`` and the
Simulation does not construct it. It is kept importable via the legacy message
types in ``src.sp2.messages.legacy_messages``.
"""

import warnings

from src.sp2.agents.agent import Agent
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.messages.legacy_messages import (
    HUpdateMessage,
    MoveMessage,
    NeighborQueryMessage,
    NeighborResponseMessage,
    NewSignalMessage,
)
from src.sp2.messages.messages import ClearedMessage

# TODO: remove this entire class
class EnvironmentAgent(Agent):
    def __init__(self, agent_id: int, grid: Grid, coordinator: Agent):
        warnings.warn(
            "EnvironmentAgent is deprecated; use src.sp2.environment.Environment.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(agent_id)
        self.grid = grid
        self.coordinator = coordinator
        self.occupancy_map: dict[Cell, int] = {}
        self.heuristic_table: dict[tuple[Cell, Cell], float] = {}  # (cell, target) -> h-value
        self.active_signals: dict[int, Signal] = {}
        self.resolved_signals: list[Signal] = []
        self.base: Cell | None = None
        self.agent_registry: dict[int, Agent] = {}

    def register_rescue_agents(self, rescue_agents: list[Agent]) -> None:
        """Register rescue agents so we can send responses back to them."""
        for agent in rescue_agents:
            self.agent_registry[agent.agent_id] = agent

    def initialize(self, signals: list[Signal], base: Cell, rescue_agent_positions: dict[int, Cell]) -> None:
        """Initialize the grid cell types and heuristic table."""
        self.base = base

        # 1. Set cell types in Grid
        self.grid.set_cell_type(base, CellType.BASE)
        for sig in signals:
            self.grid.set_cell_type(sig.location, CellType.SIGNAL)
        for _, pos in rescue_agent_positions.items():
            if pos != base:
                self.grid.set_cell_type(pos, CellType.AGENT)

        # 2. Initialize heuristic table with (cell, target) keys
        self.heuristic_table.clear()
        for cell in self.grid.all_cells():
            if self.grid.get_cell_type(cell) == CellType.OBSTACLE:
                continue
            for sig in signals:
                self.heuristic_table[(cell, sig.location)] = float(cell.manhattan_distance(sig.location))
            self.heuristic_table[(cell, base)] = float(cell.manhattan_distance(base))

        # 3. Populate occupancy map
        self.occupancy_map = {pos: aid for aid, pos in rescue_agent_positions.items()}
        self.active_signals = {sig.signal_id: sig for sig in signals}
        self.resolved_signals = []

    def select_actions(self, tick: int) -> list:
        """Deprecated: the legacy environment never participated in the
        perceive -> decide -> act loop. Retained only to satisfy the abstract
        base; the live system uses Environment instead."""
        raise NotImplementedError("EnvironmentAgent is deprecated; use Environment.")

    def step(self, tick: int) -> None:  # type: ignore[override]
        """Process inbox messages (legacy message-round-trip design)."""
        messages = self.drain_inbox()
        for msg in messages:
            if isinstance(msg, ClearedMessage):
                # Move signal to resolved signals
                for sig_id, sig in list(self.active_signals.items()):
                    if sig.location == msg.signal:
                        sig.resolved_at_tick = tick
                        sig.resolved_by = msg.sender_id
                        self.resolved_signals.append(sig)
                        del self.active_signals[sig_id]
                self.grid.set_cell_type(msg.signal, CellType.FREE)

            elif isinstance(msg, HUpdateMessage):
                # Only update if target is provided
                if msg.target:
                    self.heuristic_table[(msg.cell, msg.target)] = msg.value

            elif isinstance(msg, MoveMessage):
                # Update occupancy map
                if msg.from_cell in self.occupancy_map and self.occupancy_map[msg.from_cell] == msg.sender_id:
                    del self.occupancy_map[msg.from_cell]
                self.occupancy_map[msg.to_cell] = msg.sender_id

                # Update grid cell types
                if msg.from_cell == self.base:
                    self.grid.set_cell_type(msg.from_cell, CellType.BASE)
                elif any(sig.location == msg.from_cell for sig in self.active_signals.values()):
                    self.grid.set_cell_type(msg.from_cell, CellType.SIGNAL)
                else:
                    self.grid.set_cell_type(msg.from_cell, CellType.FREE)
                self.grid.set_cell_type(msg.to_cell, CellType.AGENT)

            elif isinstance(msg, NeighborQueryMessage):
                # Build NeighborResponseMessage
                neighbors_data = []
                for neighbor in self.grid.get_passable_neighbors(msg.position):
                    h_val = 0.0
                    if msg.target:
                        h_val = self.heuristic_table.get(
                            (neighbor, msg.target), float(neighbor.manhattan_distance(msg.target))
                        )
                    cell_type = self.grid.get_cell_type(neighbor)
                    neighbors_data.append((neighbor, cell_type, h_val))

                response = NeighborResponseMessage(
                    sender_id=self.agent_id, receiver_id=msg.sender_id, tick=tick, neighbors=neighbors_data
                )

                # Send to sender
                if msg.sender_id in self.agent_registry:
                    self.send_message(self.agent_registry[msg.sender_id], response)

    def inject_dynamic_signal(self, signal: Signal, tick: int) -> None:
        """Inject a dynamic signal into the grid."""
        self.grid.set_cell_type(signal.location, CellType.SIGNAL)
        self.active_signals[signal.signal_id] = signal

        # Populate heuristic table for this new target
        for cell in self.grid.all_cells():
            if self.grid.get_cell_type(cell) == CellType.OBSTACLE:
                continue
            self.heuristic_table[(cell, signal.location)] = float(cell.manhattan_distance(signal.location))

        # Send NewSignalMessage to Coordinator
        msg = NewSignalMessage(
            sender_id=self.agent_id, receiver_id=self.coordinator.agent_id, tick=tick, location=signal.location
        )
        self.send_message(self.coordinator, msg)
