from src.sp2.algorithms.lrta_star import lrta_star_step
from src.sp2.domain.cell import Cell


def test_lrta_star_step():
    # 3 neighbors with h-values [5, 3, 7], no reservations
    cell_a = Cell(0, 1)
    cell_b = Cell(1, 0)
    cell_c = Cell(1, 2)
    neighbors = [(cell_a, 5.0), (cell_b, 3.0), (cell_c, 7.0)]

    updated_h, best_move = lrta_star_step(4.0, neighbors, set())
    assert updated_h == 4.0  # min_j (1 + h_j) -> min(6, 4, 8) = 4.0
    assert best_move == cell_b

    # Same but the h=3 neighbor (cell_b) is reserved
    updated_h, best_move = lrta_star_step(4.0, neighbors, {cell_b})
    assert updated_h == 4.0  # h is still computed using ALL neighbors
    assert best_move == cell_a  # cell_a has lower f-value than cell_c

    # All neighbors reserved
    updated_h, best_move = lrta_star_step(4.0, neighbors, {cell_a, cell_b, cell_c})
    assert updated_h == 4.0
    assert best_move is None

    # Single neighbor
    single_neighbor = [(cell_a, 5.0)]
    updated_h, best_move = lrta_star_step(3.0, single_neighbor, set())
    assert updated_h == 6.0
    assert best_move == cell_a


def test_lrta_star_monotone():
    # Verify h never decreases even when neighbors' h-values decrease (representing a bad environment/outdated data, but lrta-star should be monotonic)
    cell_a = Cell(0, 1)
    neighbors1 = [(cell_a, 5.0)]
    h1, _ = lrta_star_step(2.0, neighbors1, set())
    assert h1 == 6.0

    neighbors2 = [(cell_a, 3.0)]  # h-value of neighbor decreased
    h2, _ = lrta_star_step(h1, neighbors2, set())
    assert h2 == 6.0  # should stay 6.0, not decrease to 4.0!
