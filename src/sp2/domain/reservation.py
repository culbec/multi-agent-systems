from dataclasses import dataclass

from src.sp2.domain.cell import Cell


@dataclass(frozen=True)
class Reservation:
    agent_id: int
    cell: Cell
    tick: int
