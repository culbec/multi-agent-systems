import math
import random
from collections import deque

from src.sp2.config import SimulationConfig
from src.sp2.defaults import (
    DEFAULT_AGENT_COUNT,
    DEFAULT_COLS,
    DEFAULT_DYNAMIC_DURATION,
    DEFAULT_DYNAMIC_FREQUENCY,
    DEFAULT_INITIAL_SIGNALS,
    DEFAULT_MAX_TICKS,
    DEFAULT_OBSTACLE_DENSITY,
    DEFAULT_ROWS,
    DEFAULT_SEED,
)


def sample_poisson(lam: float) -> int:
    if lam <= 0.0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def generate_config(
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    obstacle_density: float = DEFAULT_OBSTACLE_DENSITY,  # 0.0 to 0.4
    num_signals: int = DEFAULT_INITIAL_SIGNALS,
    agent_count: int = DEFAULT_AGENT_COUNT,
    base_location: tuple[int, int] | None = None,  # None = center
    dynamic_signal_frequency: float = DEFAULT_DYNAMIC_FREQUENCY,  # avg signals per tick (Poisson)
    dynamic_signal_duration: int = DEFAULT_DYNAMIC_DURATION,  # ticks over which dynamic signals appear
    max_ticks: int = DEFAULT_MAX_TICKS,
    seed: int = DEFAULT_SEED,
) -> SimulationConfig:
    """
    Generates a valid, fully connected SimulationConfig.
    """
    random.seed(seed)

    if base_location is None:
        base_location = (rows // 2, cols // 2)

    # 1. Place obstacles randomly based on density
    obstacle_coords = set()
    for r in range(rows):
        for c in range(cols):
            if (r, c) == base_location:
                continue
            if random.random() < obstacle_density:
                obstacle_coords.add((r, c))

    # 2. Identify reachable cells from base via BFS
    def get_reachable(obstacles):
        reachable = {base_location}
        queue = deque([base_location])
        while queue:
            curr = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = curr[0] + dr, curr[1] + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    neighbor = (nr, nc)
                    if neighbor not in obstacles and neighbor not in reachable:
                        reachable.add(neighbor)
                        queue.append(neighbor)
        return reachable

    reachable = get_reachable(obstacle_coords)

    # 3. Connect all unreachable free cells to the base
    unreachable_free = []
    for r in range(rows):
        for c in range(cols):
            cell = (r, c)
            if cell not in obstacle_coords and cell not in reachable:
                unreachable_free.append(cell)

    if unreachable_free:
        # Find shortest paths to base for all cells (BFS on an empty grid from base)
        parent = {}
        queue = deque([base_location])
        visited = {base_location}
        while queue:
            curr = queue.popleft()
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = curr[0] + dr, curr[1] + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    neighbor = (nr, nc)
                    if neighbor not in visited:
                        visited.add(neighbor)
                        parent[neighbor] = curr
                        queue.append(neighbor)

        # For each unreachable cell, clear obstacles along the shortest path to base
        for cell in unreachable_free:
            curr = cell
            while curr != base_location:
                if curr in obstacle_coords:
                    obstacle_coords.remove(curr)
                curr = parent[curr]

    # 4. Place initial signals at random free cells
    all_free_cells = []
    for r in range(rows):
        for c in range(cols):
            cell = (r, c)
            if cell != base_location and cell not in obstacle_coords:
                all_free_cells.append(cell)

    actual_num_signals = min(num_signals, len(all_free_cells))
    initial_signals = random.sample(all_free_cells, actual_num_signals)

    # 5. Generate dynamic signal stream
    dynamic_signal_stream = []
    # Refresh free cells list to exclude initial signals
    all_free_cells = [cell for cell in all_free_cells if cell not in initial_signals]

    for tick in range(1, dynamic_signal_duration + 1):
        if not all_free_cells:
            break
        num_dyn_signals = sample_poisson(dynamic_signal_frequency)
        if num_dyn_signals > 0:
            num_to_place = min(num_dyn_signals, len(all_free_cells))
            placed = random.sample(all_free_cells, num_to_place)
            for r, c in placed:
                dynamic_signal_stream.append((r, c, tick))
                # Do NOT remove (r, c) from all_free_cells so that they can get in trouble again in future ticks!

    return SimulationConfig(
        rows=rows,
        cols=cols,
        obstacle_coords=sorted(list(obstacle_coords)),
        base_location=base_location,
        initial_signals=initial_signals,
        agent_count=agent_count,
        dynamic_signal_stream=dynamic_signal_stream,
        max_ticks=max_ticks,
        seed=seed,
    )
