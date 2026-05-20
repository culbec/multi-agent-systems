import numpy as np


def compute_statistics(frames: list[dict], resolved_signals: list, rescue_agents: list, total_ticks: int) -> dict:
    """
    Computes detailed statistics for the simulation run.
    """
    makespan = 0
    if resolved_signals:
        makespan = max(sig.resolved_at_tick for sig in resolved_signals if sig.resolved_at_tick is not None)

    # 1. Average resolution time
    resolution_times = [
        sig.resolved_at_tick - sig.created_at_tick for sig in resolved_signals if sig.resolved_at_tick is not None
    ]
    avg_resolution_time = float(np.mean(resolution_times)) if resolution_times else 0.0

    # 2. Per-agent metrics
    per_agent = []
    for a in rescue_agents:
        agent_id = a.agent_id

        # Analyze frames to calculate idle ticks and wait/conflict ticks
        idle_ticks = 0
        wait_ticks = 0
        moving_ticks = 0
        halted_ticks = 0

        for frame in frames:
            for agent_info in frame["agents"]:
                if agent_info["id"] == agent_id:
                    state = agent_info["state"]
                    if state == "idle":
                        idle_ticks += 1
                    elif state == "waiting":
                        wait_ticks += 1
                    elif state == "moving":
                        moving_ticks += 1
                    elif state == "halted":
                        halted_ticks += 1

        total_active_ticks = idle_ticks + wait_ticks + moving_ticks
        idle_ratio = idle_ticks / total_active_ticks if total_active_ticks > 0 else 0.0

        resolved_count = sum(1 for sig in resolved_signals if sig.resolved_by == agent_id)

        per_agent.append(
            {
                "id": agent_id,
                "steps": len(a.movement_history) - 1,
                "signals_resolved": resolved_count,
                "wait_ticks": wait_ticks,
                "idle_ticks": idle_ticks,
                "idle_ratio": idle_ratio,
                "trajectory": [(c.row, c.col) for c in a.movement_history],
            }
        )

    # 3. Resolution log
    resolution_log = [
        {
            "signal": (sig.location.row, sig.location.col),
            "resolved_by": sig.resolved_by,
            "created_at": sig.created_at_tick,
            "resolved_at": sig.resolved_at_tick,
            "duration": sig.resolved_at_tick - sig.created_at_tick,
        }
        for sig in sorted(resolved_signals, key=lambda s: s.resolved_at_tick or 0)
    ]

    # 4. Heuristic convergence (optional tracking of h-value change)
    h_changes = []
    for t in range(1, len(frames)):
        prev_map = frames[t - 1]["heuristic_map"]
        curr_map = frames[t]["heuristic_map"]

        # Find overlap
        shared_keys = set(prev_map.keys()) & set(curr_map.keys())
        if shared_keys:
            diffs = [abs(curr_map[k] - prev_map[k]) for k in shared_keys]
            h_changes.append(float(np.mean(diffs)))
        else:
            h_changes.append(0.0)

    mean_heuristic_change = float(np.mean(h_changes)) if h_changes else 0.0

    return {
        "makespan": makespan,
        "total_steps": sum(len(a.movement_history) - 1 for a in rescue_agents),
        "total_ticks": total_ticks,
        "signals_resolved": len(resolved_signals),
        "avg_resolution_time": avg_resolution_time,
        "mean_heuristic_change": mean_heuristic_change,
        "per_agent": per_agent,
        "resolution_log": resolution_log,
    }
