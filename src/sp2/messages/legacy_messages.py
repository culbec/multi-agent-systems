"""DEPRECATED message types.

These message classes belonged to the pre-PAGE design, where the Environment
was an ``Agent`` and perception/mutation happened over message round-trips. They
are retained **only** to keep the deprecated :class:`EnvironmentAgent` importable
for reference. The live PAGE system does not use them:

* ``NEIGHBOR_QUERY``/``NEIGHBOR_RESPONSE`` -> ``NeighborSensor`` reads the world
* ``MOVE`` -> ``MoveAction`` -> ``Environment.move``
* ``H_UPDATE`` -> ``UpdateHeuristicAction`` -> ``Environment.update_heuristic``
* ``NEW_SIGNAL`` -> ``NewSignalSensor`` diff (Decision D2)
* ``RESERVE`` -> ``Environment.reserve`` (Decision D1, Option A)
"""

from dataclasses import dataclass

from src.sp2.domain.cell import Cell, CellType
from src.sp2.messages.messages import Message

# TODO: remove this entire class
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
class NewSignalMessage(Message):
    location: Cell
    msg_type: str = "NEW_SIGNAL"