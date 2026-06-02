from dataclasses import dataclass
from enum import IntEnum


class CellType(IntEnum):
    FREE = 0
    SIGNAL = 1
    OBSTACLE = 2
    AGENT = 3
    BASE = 4
    SIGNAL_RESOLVED = 5


@dataclass(frozen=True)
class Cell:
    row: int
    col: int

    def manhattan_distance(self, other: "Cell") -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)
