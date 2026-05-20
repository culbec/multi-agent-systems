from dataclasses import dataclass

from src.sp2.domain.cell import Cell


@dataclass
class Signal:
    signal_id: int
    location: Cell
    created_at_tick: int
    resolved_at_tick: int | None = None
    resolved_by: int | None = None  # agent_id
