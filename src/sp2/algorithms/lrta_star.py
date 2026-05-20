from src.sp2.domain.cell import Cell


def lrta_star_step(
    current_h: float,
    neighbors: list[tuple[Cell, float]],  # (cell, h_value) pairs for passable neighbors
    reserved_cells: set[Cell],  # cells reserved by peers this tick
) -> tuple[float, Cell | None]:
    """
    Returns:
        updated_h: new h-value for the current cell (h(i) <- min_j [1 + h(j)])
        best_move: cell to move to, or None if all neighbors blocked/reserved

    The move cost k(i,j) = 1 for all grid moves (uniform cost).
    """
    if not neighbors:
        return current_h, None

    # Compute f-values
    f_values = [(cell, 1.0 + h) for cell, h in neighbors]

    # h-update: minimum f across ALL neighbors (including reserved ones), but never decreasing below current_h
    min_f = min(f for _, f in f_values)
    updated_h = max(current_h, min_f)

    # Move selection: exclude reserved cells
    available = [(cell, f) for cell, f in f_values if cell not in reserved_cells]
    if not available:
        return updated_h, None  # all neighbors reserved -> wait

    # Break ties by (f-value, row, col) for determinism
    best_move = min(available, key=lambda x: (x[1], x[0].row, x[0].col))[0]
    return updated_h, best_move
