from dataclasses import dataclass, field

from src.sp2.domain.cell import Cell
from src.sp2.domain.grid import Grid
from src.sp2.domain.reservation import Reservation
from src.sp2.domain.signal import Signal


@dataclass
class State:
    """The complete, objective representation of the world (AIMA `State`).

    This is the situation that the ``env: S x A -> S`` function transforms. It
    holds *physical* facts only -- where things are -- never an agent's beliefs,
    goals, or memory. In particular an agent's position lives here (in
    ``positions``), not on the agent: position is a world fact the environment
    enforces (single-occupancy, reservations) and that any agent could observe.

    The ``State`` is owned by the :class:`Environment`, which is the only place
    its invariants are enforced. Agents read it exclusively through perception
    (``Environment.get_percept``) and mutate it exclusively through the
    Environment's guarded primitives (invoked by ``Action`` objects).
    """

    grid: Grid
    base: Cell | None = None
    # agent_id -> cell. Authoritative position registry (several agents may
    # share the base cell, so this maps per-agent rather than per-cell).
    positions: dict[int, Cell] = field(default_factory=dict)
    # (cell, target) -> learned h-value
    heuristic_table: dict[tuple[Cell, Cell], float] = field(default_factory=dict)
    active_signals: dict[int, Signal] = field(default_factory=dict)
    resolved_signals: list[Signal] = field(default_factory=list)
    # tick -> reservations claimed for that tick (Decision D1, Option A)
    reservations: dict[int, set[Reservation]] = field(default_factory=dict)

    def position_of(self, agent_id: int) -> Cell | None:
        """The authoritative cell an agent currently occupies."""
        return self.positions.get(agent_id)

    def occupant(self, cell: Cell) -> int | None:
        """The id of an agent occupying ``cell`` (the base may hold several;
        this returns the first found, which is sufficient for the
        single-occupancy check that exempts the base)."""
        for agent_id, occupied in self.positions.items():
            if occupied == cell:
                return agent_id
        return None

    def display(self) -> str:
        """Text rendering of the world (the example's ``State.display``)."""
        lines = []
        for r in range(self.grid.rows):
            row = []
            for c in range(self.grid.cols):
                cell = self.grid.get_cell(r, c)
                agent_id = self.occupant(cell)
                row.append(f"A{agent_id}" if agent_id is not None else str(int(self.grid.get_cell_type(cell))))
            lines.append(" ".join(row))
        return "\n".join(lines)