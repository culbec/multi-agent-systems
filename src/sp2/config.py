import json
from dataclasses import asdict, dataclass

from src.sp2.defaults import DEFAULT_MAX_TICKS, DEFAULT_SEED


@dataclass
class SimulationConfig:
    rows: int
    cols: int
    obstacle_coords: list[tuple[int, int]]
    base_location: tuple[int, int]
    initial_signals: list[tuple[int, int]]
    agent_count: int
    dynamic_signal_stream: list[tuple[int, int, int]]  # (row, col, tick)
    max_ticks: int = DEFAULT_MAX_TICKS
    seed: int = DEFAULT_SEED

    def to_json(self, filepath: str) -> None:
        """Saves the config to a JSON file."""
        data = asdict(self)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> "SimulationConfig":
        """Loads a pre-generated layout SimulationConfig from a JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)

        # Convert list coords back to tuples for hashing / value matching
        obstacle_coords = [tuple(coord) for coord in data.get("obstacle_coords", [])]
        base_location = tuple(data["base_location"]) if "base_location" in data else None
        initial_signals = [tuple(sig) for sig in data.get("initial_signals", [])]
        dynamic_signal_stream = [tuple(item) for item in data.get("dynamic_signal_stream", [])]

        return cls(
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
