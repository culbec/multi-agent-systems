from dataclasses import dataclass

from src.sp2.domain.cell import Cell
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import Message
from src.sp2.perceptions.percept import Percept


@dataclass(frozen=True)
class RescuePercept(Percept):
    """What a rescue agent perceives: its own position, where it is headed, the
    passable neighborhood (focused on the destination), the cells it must treat
    as reserved this tick, and the inter-agent messages addressed to it.

    The neighborhood is already focused on ``destination`` and already has
    cells occupied by idle peers parked at base filtered out -- that read
    orchestration lives in the sensors, not in the agent.
    """

    position: Cell | None
    destination: Cell | None
    # h(position, destination) from the heuristic table; seeds the agent's
    # current_h so the learned (monotone) value is never reset below the table.
    position_h: float | None
    neighbors: tuple[tuple[Cell, float], ...]  # (cell, h_to_destination)
    reserved_cells: frozenset[Cell]
    messages: tuple[Message, ...]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"RescuePercept(pos={self.position}, dest={self.destination}, "
            f"neighbors={len(self.neighbors)}, reserved={len(self.reserved_cells)}, "
            f"msgs={len(self.messages)})"
        )


@dataclass(frozen=True)
class CoordinatorPercept(Percept):
    """What the coordinator perceives: signals that have newly appeared in the
    world since it last looked (diffed from ``active_signals``, Decision D2) and
    the inter-agent messages addressed to it."""

    new_signals: tuple[Signal, ...]
    messages: tuple[Message, ...]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"CoordinatorPercept(new_signals={len(self.new_signals)}, msgs={len(self.messages)})"