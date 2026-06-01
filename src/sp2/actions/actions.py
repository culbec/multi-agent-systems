from typing import TYPE_CHECKING

from src.sp2.actions.action import CommunicativeAction, EnvironmentAction
from src.sp2.domain.cell import Cell
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    TerminateMessage,
)

if TYPE_CHECKING:
    from src.sp2.agents.agent import Agent
    from src.sp2.environment.environment import Environment


# Environment actions: mutate the world (and the acting agent's memory)
class MoveAction(EnvironmentAction):
    """Move the agent one cell. Acts on the world (occupancy + cell types via
    ``env.move``) *and* on the agent's own memory (current_h + movement trail)."""

    def __init__(self, from_cell: Cell, to_cell: Cell, new_h: float):
        self.from_cell = from_cell
        self.to_cell = to_cell
        self.new_h = new_h

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        env.move(agent.agent_id, self.from_cell, self.to_cell)
        agent.current_h = self.new_h
        agent.movement_history.append(self.to_cell)

    def __str__(self) -> str:
        return f"MOVE {self.from_cell} -> {self.to_cell}"


class UpdateHeuristicAction(EnvironmentAction):
    """Write the LRTA* learned estimate for the agent's current cell into the
    shared heuristic table (guarded for monotonicity) and the agent's current_h."""

    def __init__(self, cell: Cell, target: Cell, value: float):
        self.cell = cell
        self.target = target
        self.value = value

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        env.update_heuristic(self.cell, self.target, self.value)
        agent.current_h = self.value

    def __str__(self) -> str:  # pragma: no cover
        return f"H_UPDATE {self.cell}->{self.target}={self.value}"


class ReserveAction(EnvironmentAction):
    """Claim a cell in the Environment's reservation table for this tick
    (Decision D1, Option A)."""

    def __init__(self, cell: Cell, tick: int):
        self.cell = cell
        self.reserve_tick = tick

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        env.reserve(agent.agent_id, self.cell, self.reserve_tick)

    def __str__(self) -> str:  # pragma: no cover
        return f"RESERVE {self.cell}@{self.reserve_tick}"


class ClearSignalAction(EnvironmentAction):
    """Resolve the signal the agent is standing on (world mutation) and announce
    it to peers and the coordinator (communication). A composite effect."""

    def __init__(self, signal_cell: Cell, tick: int):
        self.signal_cell = signal_cell
        self.tick = tick

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        env.resolve_signal(self.signal_cell, agent.agent_id, self.tick)
        cleared = ClearedMessage(sender_id=agent.agent_id, receiver_id=-1, tick=tick, signal=self.signal_cell)
        for peer in agent.peers:
            agent.send_message(peer, cleared)
        agent.send_message(agent.coordinator, cleared)

    def __str__(self) -> str:  # pragma: no cover
        return f"CLEAR {self.signal_cell}"


# Communicative actions: send a surviving inter-agent message.
class ReportFreeAction(CommunicativeAction):
    """Tell the coordinator this agent is available."""

    def __init__(self, position: Cell):
        self.position = position

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        free = FreeMessage(
            sender_id=agent.agent_id,
            receiver_id=agent.coordinator.agent_id,
            tick=tick,
            agent_id=agent.agent_id,
            position=self.position,
        )
        agent.send_message(agent.coordinator, free)
        agent.free_sent = True

    def __str__(self) -> str:  # pragma: no cover
        return f"REPORT_FREE {self.position}"


class AssignAction(CommunicativeAction):
    """Coordinator tells a rescue agent which signal to head for."""

    def __init__(self, target_agent_id: int, target: Cell):
        self.target_agent_id = target_agent_id
        self.target = target

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        assign = AssignMessage(
            sender_id=agent.agent_id, receiver_id=self.target_agent_id, tick=tick, target=self.target
        )
        agent.send_message(agent.agent_registry[self.target_agent_id], assign)

    def __str__(self) -> str:  # pragma: no cover
        return f"ASSIGN {self.target_agent_id}->{self.target}"


class TerminateAction(CommunicativeAction):
    """Coordinator halts the whole rescue team."""

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        for rescue in agent.rescue_agents:
            agent.send_message(
                rescue, TerminateMessage(sender_id=agent.agent_id, receiver_id=rescue.agent_id, tick=tick)
            )

    def __str__(self) -> str:  # pragma: no cover
        return "TERMINATE"


# Control action: yield this tick.
class WaitAction(EnvironmentAction):
    """Yield: no world effect, just record that the agent waited."""

    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        agent.wait_count += 1

    def __str__(self) -> str:  # pragma: no cover
        return "WAIT"
