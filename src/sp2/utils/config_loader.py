import json

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


def load_any_config(filepath: str) -> tuple[SimulationConfig | None, dict | None]:
    """
    Loads configuration from a JSON file.
    Detects whether the JSON file is a concrete SimulationConfig layout
    or a generator parameter set.

    Returns:
        (SimulationConfig, None) if concrete config
        (None, dict_params) if parameter config
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    # Check if this is a concrete layout (has obstacle_coords or base_location)
    if "obstacle_coords" in data or "base_location" in data:
        obstacle_coords = [tuple(coord) for coord in data.get("obstacle_coords", [])]
        base_location = (
            tuple(data["base_location"]) if "base_location" in data else (data["rows"] // 2, data["cols"] // 2)
        )
        initial_signals = [tuple(sig) for sig in data.get("initial_signals", [])]
        dynamic_signal_stream = [tuple(item) for item in data.get("dynamic_signal_stream", [])]

        config = SimulationConfig(
            rows=data["rows"],
            cols=data["cols"],
            obstacle_coords=obstacle_coords,
            base_location=base_location,
            initial_signals=initial_signals,
            agent_count=data["agent_count"],
            dynamic_signal_stream=dynamic_signal_stream,
            max_ticks=data.get("max_ticks", DEFAULT_MAX_TICKS),
            seed=data.get("seed", DEFAULT_SEED),
        )
        return config, None
    else:
        # It's a generator parameters dictionary
        params = {
            "rows": data.get("rows", DEFAULT_ROWS),
            "cols": data.get("cols", DEFAULT_COLS),
            "obstacle_density": data.get("obstacle_density", DEFAULT_OBSTACLE_DENSITY),
            "num_signals": data.get("num_signals", DEFAULT_INITIAL_SIGNALS),
            "agent_count": data.get("agent_count", DEFAULT_AGENT_COUNT),
            "dynamic_signal_frequency": data.get("dynamic_signal_frequency", DEFAULT_DYNAMIC_FREQUENCY),
            "dynamic_signal_duration": data.get("dynamic_signal_duration", DEFAULT_DYNAMIC_DURATION),
            "max_ticks": data.get("max_ticks", DEFAULT_MAX_TICKS),
            "seed": data.get("seed", DEFAULT_SEED),
        }
        return None, params
