from collections import deque

from src.sp2.utils.grid_generator import generate_config


def test_grid_generator_connectivity():
    # Generate config with 20% obstacles
    config = generate_config(
        rows=15,
        cols=15,
        obstacle_density=0.25,
        num_signals=8,
        agent_count=4,
        dynamic_signal_frequency=0.5,
        dynamic_signal_duration=10,
        seed=123,
    )

    # Verify basic config parameters
    assert config.rows == 15
    assert config.cols == 15
    assert len(config.initial_signals) == 8
    assert config.agent_count == 4

    # Verify connectivity: Every non-obstacle cell must be reachable from base
    base = config.base_location
    obstacles = set(config.obstacle_coords)

    reachable = {base}
    queue = deque([base])
    while queue:
        curr = queue.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = curr[0] + dr, curr[1] + dc
            if 0 <= nr < 15 and 0 <= nc < 15:
                neighbor = (nr, nc)
                if neighbor not in obstacles and neighbor not in reachable:
                    reachable.add(neighbor)
                    queue.append(neighbor)

    for r in range(15):
        for c in range(15):
            cell = (r, c)
            if cell not in obstacles:
                assert cell in reachable, f"Cell {cell} is not reachable from base {base}"
