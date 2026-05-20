from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid


def test_manhattan_distance():
    c1 = Cell(0, 0)
    c2 = Cell(3, 4)
    assert c1.manhattan_distance(c2) == 7
    assert c2.manhattan_distance(c1) == 7


def test_grid_neighbors():
    grid = Grid(5, 5)
    # Put an obstacle at (1, 1) and (1, 2)
    grid.set_cell_type(grid.get_cell(1, 1), CellType.OBSTACLE)
    grid.set_cell_type(grid.get_cell(1, 2), CellType.OBSTACLE)

    # Corner neighbors (0, 0)
    # Passable neighbors should be (1, 0) and (0, 1). Note (1, 1) is an obstacle.
    neighbors_0_0 = grid.get_passable_neighbors(Cell(0, 0))
    assert Cell(1, 0) in neighbors_0_0
    assert Cell(0, 1) in neighbors_0_0
    assert Cell(1, 1) not in neighbors_0_0
    assert len(neighbors_0_0) == 2

    # Neighbors adjacent to obstacles at (0, 1)
    # Neighbors of (0, 1) are (0, 0), (0, 2), (1, 1)[OBSTACLE]
    neighbors_0_1 = grid.get_passable_neighbors(Cell(0, 1))
    assert Cell(0, 0) in neighbors_0_1
    assert Cell(0, 2) in neighbors_0_1
    assert Cell(1, 1) not in neighbors_0_1
    assert len(neighbors_0_1) == 2

    # Check is_passable
    assert not grid.is_passable(Cell(1, 1))
    assert grid.is_passable(Cell(0, 0))
