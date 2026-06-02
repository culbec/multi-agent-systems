from typing import TYPE_CHECKING

from src.sp2.agents.agent import Agent
from src.sp2.agents.coordinator_agent import CoordinatorAgent
from src.sp2.agents.rescue_agent import RescueAgent
from src.sp2.config import SimulationConfig
from src.sp2.domain.cell import Cell, CellType
from src.sp2.domain.grid import Grid
from src.sp2.domain.signal import Signal
from src.sp2.environment.environment import Environment
from src.sp2.utils.stats import compute_statistics

if TYPE_CHECKING:
    from src.sp2.messages.messages import Message


class Simulation:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.environment: Environment | None = None
        self.coordinator: CoordinatorAgent | None = None
        self.rescue_agents: list[RescueAgent] = []
        self.grid: Grid | None = None

        self.tick: int = 0
        self.terminated: bool = False
        self.termination_reason: str = "Running"
        self.frames: list[dict] = []
        self.dynamic_signal_queue: list[tuple[int, int, int]] = []
        self.tick_messages: "list[Message]" = []
        # Signal id minting lives in the Simulation now (it owns the dynamic queue)
        self.next_signal_id: int = 1

    def setup(self) -> None:
        """Initialize the grid, signals, agents, and wire their connections."""
        self.tick = 0
        self.terminated = False
        self.termination_reason = "Running"
        self.frames.clear()
        self.tick_messages: "list[Message]" = []

        # Enable message logging
        Agent.message_callback = self.tick_messages.append

        # 1. Create Grid from config
        self.grid = Grid(self.config.rows, self.config.cols)
        for r, c in self.config.obstacle_coords:
            self.grid.set_cell_type(self.grid.get_cell(r, c), CellType.OBSTACLE)

        base_cell = self.grid.get_cell(*self.config.base_location)
        self.grid.set_cell_type(base_cell, CellType.BASE)

        # 2. Create signals from initial_signals
        signals = []
        for i, (r, c) in enumerate(self.config.initial_signals):
            signals.append(Signal(signal_id=i + 1, location=self.grid.get_cell(r, c), created_at_tick=0))

        # 3. Create the Environment (plain state authority, not an agent)
        self.environment = Environment(self.grid)

        # 4. Create Rescue Agents (all start at base; position is world state)
        self.rescue_agents = []
        for i in range(self.config.agent_count):
            agent = RescueAgent(agent_id=i, start_position=base_cell, coordinator=None, peers=[])
            self.rescue_agents.append(agent)

        # 5. Create Coordinator Agent
        self.coordinator = CoordinatorAgent(agent_id=-2, rescue_agents=self.rescue_agents)

        # 6. Wire references (the Environment talks to no one)
        for agent in self.rescue_agents:
            agent.coordinator = self.coordinator
            agent.peers = [peer for peer in self.rescue_agents if peer.agent_id != agent.agent_id]

        # 7. Initialize Environment and Coordinator
        rescue_positions = {a.agent_id: base_cell for a in self.rescue_agents}
        self.environment.initialize(signals, base_cell, rescue_positions)
        self.coordinator.initialize(signals)

        # 8. Dynamic signal queue + id minting state
        self.next_signal_id = (max(sig.signal_id for sig in signals) + 1) if signals else 1
        self.dynamic_signal_queue = sorted(self.config.dynamic_signal_stream, key=lambda x: x[2])
        self.coordinator.no_more_dynamic_signals = len(self.dynamic_signal_queue) == 0

    def advance_tick(self) -> None:
        """Execute one simulation tick."""
        if self.terminated:
            return

        self.tick += 1

        # Clear messages from the previous tick and prepare to log new ones
        self.tick_messages.clear()
        Agent.message_callback = self.tick_messages.append

        # 1. Inject dynamic signals scheduled for this tick
        while self.dynamic_signal_queue and self.dynamic_signal_queue[0][2] == self.tick:
            r, c, _ = self.dynamic_signal_queue.pop(0)
            signal = Signal(
                signal_id=self.next_signal_id,
                location=self.grid.get_cell(r, c),
                created_at_tick=self.tick,
            )
            self.next_signal_id += 1
            self.environment.inject_signal(signal)

        if not self.dynamic_signal_queue:
            self.coordinator.no_more_dynamic_signals = True

        # 2. Coordinator: perceive -> decide -> act (assignments dispatched now)
        self.coordinator.step(self.environment, self.tick)

        # 3. Record positions before the rescue pass (waiting/moving detection)
        positions_before = {a.agent_id: self.environment.position_of(a.agent_id) for a in self.rescue_agents}

        # 4. Single ordered pass: rescue agents act in descending id order, so a
        #    higher-id agent reserves/moves before a lower-id agent perceives and
        #    yields, guaranteeing no dual occupancy without a sub-phase split
        for agent in sorted(self.rescue_agents, key=lambda a: a.agent_id, reverse=True):
            agent.step(self.environment, self.tick)

        # 5. Snapshot the cells reserved this tick (world state now, not
        # messages), then run reservation housekeeping (Decision D1, Option A)
        reserved_cells = self.environment.reservations(self.tick)
        self.environment.clear_reservations(self.tick)

        # 6. Record frame (positions_before assists state determination;
        #    reserved_cells lets the UI overlay reservations)
        self.frames.append(self.collect_frame(self.tick, positions_before, reserved_cells))

        # 7. Check termination
        if all(a.halted for a in self.rescue_agents):
            self.termination_reason = "All Resolved"
            self.terminated = True
        elif self.tick >= self.config.max_ticks:
            self.termination_reason = "Max Ticks Reached"
            self.terminated = True

    def run(self) -> dict:
        """Run the simulation to completion."""
        self.setup()
        while not self.terminated:
            self.advance_tick()
        return self.collect_statistics()

    def collect_frame(
        self,
        tick: int,
        positions_before: dict[int, Cell] | None = None,
        reserved_cells: "set[Cell] | None" = None,
    ) -> dict:
        """Capture the full state for one tick for UI replay."""
        # Grid types NxM matrix
        grid_types = []
        for r in range(self.config.rows):
            row_types = []
            for c in range(self.config.cols):
                row_types.append(int(self.grid.get_cell_type(self.grid.get_cell(r, c))))
            grid_types.append(row_types)

        # Rescue agents info (position is world state, read it from the env)
        agents_info = []
        for agent in self.rescue_agents:
            position = self.environment.position_of(agent.agent_id)
            if agent.halted:
                state = "halted"
            elif agent.target is None:
                state = "idle"
            elif positions_before and position == positions_before.get(agent.agent_id):
                state = "waiting"
            else:
                state = "moving"

            agents_info.append(
                {
                    "id": agent.agent_id,
                    "position": (position.row, position.col),
                    "target": (agent.target.row, agent.target.col) if agent.target else None,
                    "state": state,
                }
            )

        # Sparse heuristic map (all non-obstacle cells have finite floats)
        heuristic_map = {}
        for (cell, target), h in self.environment.heuristic_table.items():
            if any(sig.location == target for sig in self.environment.active_signals.values()):
                key = (cell.row, cell.col)
                if key not in heuristic_map or h < heuristic_map[key]:
                    heuristic_map[key] = float(h)

        active_signals = [(sig.location.row, sig.location.col) for sig in self.environment.active_signals.values()]

        # Which agent is assigned to each active signal, from the coordinator's
        # authoritative assignment table (agent_id -> Signal). JSON-friendly
        # rows [row, col, agent_id]; only signals still active are included
        active_locations = {sig.location for sig in self.environment.active_signals.values()}
        signal_assignments = [
            [sig.location.row, sig.location.col, aid]
            for aid, sig in self.coordinator.assignments.items()
            if sig.location in active_locations
        ]
        resolved_signals = [(sig.location.row, sig.location.col) for sig in self.environment.resolved_signals]

        # Format messages sent this tick
        messages_formatted = []
        for msg in self.tick_messages:
            payload = {}
            for k, v in msg.__dict__.items():
                if k not in ["sender_id", "receiver_id", "tick", "msg_type"]:
                    if isinstance(v, Cell):
                        payload[k] = (v.row, v.col)
                    elif isinstance(v, list) and v and isinstance(v[0], tuple) and isinstance(v[0][0], Cell):
                        payload[k] = [((item[0].row, item[0].col), item[1].name, item[2]) for item in v]
                    else:
                        payload[k] = v
            messages_formatted.append(
                {"type": msg.msg_type, "sender": msg.sender_id, "receiver": msg.receiver_id, "payload": payload}
            )

        return {
            "tick": tick,
            "grid_types": grid_types,
            "agents": agents_info,
            "heuristic_map": heuristic_map,
            "active_signals": active_signals,
            "signal_assignments": signal_assignments,
            "resolved_signals": resolved_signals,
            "reservations": [(cell.row, cell.col) for cell in (reserved_cells or set())],
            "messages_this_tick": messages_formatted,
        }

    def collect_statistics(self) -> dict:
        """Compile and return statistics for the simulation run."""
        stats = compute_statistics(self.frames, self.environment.resolved_signals, self.rescue_agents, self.tick)
        stats["termination_reason"] = self.termination_reason
        return stats
