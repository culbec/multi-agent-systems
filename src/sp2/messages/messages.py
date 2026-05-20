from dataclasses import dataclass

from src.sp2.domain.cell import Cell, CellType


@dataclass(kw_only=True)
class Message:
    sender_id: int
    receiver_id: int  # -1 for broadcast
    tick: int
    msg_type: str


@dataclass(kw_only=True)
class AssignMessage(Message):
    target: Cell
    msg_type: str = "ASSIGN"


@dataclass(kw_only=True)
class FreeMessage(Message):
    agent_id: int  # redundant with sender_id but explicit per spec
    position: Cell
    msg_type: str = "FREE"


@dataclass(kw_only=True)
class NeighborQueryMessage(Message):
    position: Cell
    target: Cell | None = None
    msg_type: str = "NEIGHBOR_QUERY"


@dataclass(kw_only=True)
class NeighborResponseMessage(Message):
    neighbors: list[tuple[Cell, CellType, float]]
    msg_type: str = "NEIGHBOR_RESPONSE"


@dataclass(kw_only=True)
class MoveMessage(Message):
    from_cell: Cell
    to_cell: Cell
    msg_type: str = "MOVE"


@dataclass(kw_only=True)
class HUpdateMessage(Message):
    cell: Cell
    value: float
    target: Cell | None = None
    msg_type: str = "H_UPDATE"


@dataclass(kw_only=True)
class ReserveMessage(Message):
    cell: Cell
    reserve_tick: int
    msg_type: str = "RESERVE"


@dataclass(kw_only=True)
class ClearedMessage(Message):
    signal: Cell
    msg_type: str = "CLEARED"


@dataclass(kw_only=True)
class NewSignalMessage(Message):
    location: Cell
    msg_type: str = "NEW_SIGNAL"


@dataclass(kw_only=True)
class TerminateMessage(Message):
    msg_type: str = "TERMINATE"
