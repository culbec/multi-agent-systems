from typing import Iterator

from src.sp2.domain.cell import Cell, CellType


class Grid:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.cells = [[Cell(r, c) for c in range(cols)] for r in range(rows)]
        self.cell_types = {Cell(r, c): CellType.FREE for r in range(rows) for c in range(cols)}

    def get_cell(self, r: int, c: int) -> Cell:
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.cells[r][c]
        raise ValueError(f"Cell coordinates ({r}, {c}) out of bounds")

    def set_cell_type(self, cell: Cell, cell_type: CellType) -> None:
        if cell in self.cell_types:
            self.cell_types[cell] = cell_type
        else:
            raise ValueError(f"Cell {cell} out of bounds")

    def get_cell_type(self, cell: Cell) -> CellType:
        if cell in self.cell_types:
            return self.cell_types[cell]
        raise ValueError(f"Cell {cell} out of bounds")

    def is_passable(self, cell: Cell) -> bool:
        return self.get_cell_type(cell) != CellType.OBSTACLE

    def get_passable_neighbors(self, cell: Cell) -> list[Cell]:
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = cell.row + dr, cell.col + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                neighbor = self.get_cell(nr, nc)
                if self.is_passable(neighbor):
                    neighbors.append(neighbor)
        return neighbors

    def all_cells(self) -> Iterator[Cell]:
        for r in range(self.rows):
            for c in range(self.cols):
                yield self.cells[r][c]
