from dataclasses import dataclass

from src.sp2.domain.cell import Cell

# Only *inter-agent* messages survive the PAGE refactor. Perception now reads
# the world directly (NEIGHBOR_QUERY/RESPONSE, NEW_SIGNAL), and world mutation
# flows through the Environment's guarded primitives (MOVE, H_UPDATE, RESERVE),
# so those message types are gone. The UI message log still renders these.


@dataclass(kw_only=True)
class Message:
    sender_id: int
    receiver_id: int  # -1 for broadcast
    tick: int
    msg_type: str


@dataclass(kw_only=True)
class AssignMessage(Message):
    """Coordinator -> Rescue: head for this signal. Sent by AssignAction."""

    target: Cell
    msg_type: str = "ASSIGN"


@dataclass(kw_only=True)
class FreeMessage(Message):
    """Rescue -> Coordinator: I am available. Sent by ReportFreeAction."""

    agent_id: int  # redundant with sender_id but explicit per spec
    position: Cell
    msg_type: str = "FREE"


@dataclass(kw_only=True)
class ClearedMessage(Message):
    """Rescue -> peers + Coordinator: this signal is resolved. Sent by
    ClearSignalAction (its inter-agent half)."""

    signal: Cell
    msg_type: str = "CLEARED"


@dataclass(kw_only=True)
class TerminateMessage(Message):
    """Coordinator -> Rescue: halt. Sent by TerminateAction."""

    msg_type: str = "TERMINATE"