# SP2 — Intelligent Disaster Grid Response System

You are implementing a multi-agent simulation from scratch in Python. This document is the complete specification. Each phase is self-contained: implement it fully before moving to the next. Do not use agent frameworks — all agent communication is built from scratch using in-process message queues.

---

## System Overview

A team of K autonomous **Rescue Agents** navigates an N×M grid to reach **distress signals** emitted by survivors. A single **Environment Agent** owns the grid state and shared heuristic table. A single **Coordinator Agent** assigns signals to free agents. Pathfinding uses **Learning Real-Time A\* (LRTA\*)**, a special case of Asynchronous Dynamic Programming where each agent updates h-values of visited cells. Collision avoidance uses peer-to-peer cell reservations with deterministic tie-breaking.

### Three Agent Types

- **Rescue Agent** (K instances): Moves through the grid using LRTA\*. Queries the Environment for neighbor info, broadcasts reservations to peers, notifies when a signal is cleared.
- **Coordinator Agent** (1 instance): Maintains a queue of unassigned signals. Assigns signals to free agents by nearest-first Manhattan distance. Broadcasts TERMINATE when all signals are resolved and all agents are idle.
- **Environment Agent** (1 instance): Owns the grid matrix, occupancy map, and shared h-value table. Responds to neighbor queries, processes move/heuristic updates, injects dynamic signals.

### LRTA\* Algorithm

Each Rescue Agent, at every tick:
1. Queries the Environment for passable neighbors of its current cell `i` and their h-values.
2. Computes `f(i,j) = k(i,j) + h(j)` for each neighbor `j`, where `k(i,j) = 1` (uniform cost).
3. Updates: `h(i) ← min_j f(i,j)`. Sends the updated value to the Environment Agent.
4. Selects `j* = argmin_j f(i,j)`, excluding cells reserved by peers.
5. If `j*` is contested by another agent's reservation: the agent with the **lower agent_id waits**; the higher proceeds.
6. Broadcasts `RESERVE(j*)` to all peers, sends `MOVE(j*)` to the Environment.
7. Upon reaching the target signal: broadcasts `CLEARED`, sends `FREE` to the Coordinator.

### Message Types (10 total)

| Message | Sender → Receiver | Payload |
|---|---|---|
| `ASSIGN` | Coordinator → Rescue i | `target: (r,c)` |
| `TERMINATE` | Coordinator → all | *(empty)* |
| `FREE` | Rescue i → Coordinator | `agent_id: int, position: (r,c)` |
| `NEIGHBOR_QUERY` | Rescue i → Environment | `position: (r,c)` |
| `NEIGHBOR_RESPONSE` | Environment → Rescue i | `neighbors: [(r,c, CellType, h), ...]` |
| `MOVE` | Rescue i → Environment | `from_cell: (r,c), to_cell: (r,c)` |
| `H_UPDATE` | Rescue i → Environment | `cell: (r,c), value: float` |
| `RESERVE` | Rescue i → all Rescue | `cell: (r,c), tick: int` |
| `CLEARED` | Rescue i → all agents + Environment | `signal: (r,c)` |
| `NEW_SIGNAL` | Environment → Coordinator | `location: (r,c)` |

### Tick Execution Model

Each simulation tick has two sub-phases to allow query-response within one tick:
- **Sub-phase A (queries):** All Rescue Agents send `NEIGHBOR_QUERY`. Environment Agent processes all queries and sends `NEIGHBOR_RESPONSE` replies.
- **Sub-phase B (actions):** Rescue Agents drain responses, run LRTA\*, broadcast reservations, resolve conflicts, and move. Coordinator processes `FREE`/`CLEARED`/`NEW_SIGNAL` and sends `ASSIGN`.

---

## Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| UI / Visualization | Pygame + pygame_gui |
| Simulation engine | Pure Python, no frameworks |
| Testing | pytest |

Dependencies: `pygame`, `pygame_gui`, `numpy` (optional, for grid ops), `pytest`.

---

## Project Structure

```
sp2/
├── main.py                     # Entry point: parse args or launch UI, run simulation
├── config.py                   # SimulationConfig dataclass
├── simulation.py               # Tick loop, dynamic signal injection, frame recording
│
├── domain/
│   ├── __init__.py
│   ├── cell.py                 # Cell, CellType enum
│   ├── grid.py                 # Grid class
│   ├── signal.py               # Signal dataclass
│   └── reservation.py          # Reservation dataclass
│
├── agents/
│   ├── __init__.py
│   ├── agent.py                # Abstract Agent base class
│   ├── environment_agent.py    # EnvironmentAgent
│   ├── coordinator_agent.py    # CoordinatorAgent
│   └── rescue_agent.py         # RescueAgent
│
├── messages/
│   ├── __init__.py
│   └── messages.py             # Message base + 10 concrete message dataclasses
│
├── algorithms/
│   ├── __init__.py
│   └── lrta_star.py            # Pure LRTA* step function
│
├── utils/
│   ├── __init__.py
│   ├── grid_generator.py       # Procedural grid generation with reachability checks
│   └── stats.py                # Statistics collection and aggregation
│
├── ui/
│   ├── __init__.py
│   ├── renderer.py             # Pygame grid renderer: cells, agents, overlays
│   ├── controls.py             # pygame_gui config panel: sliders, buttons, toggles
│   ├── playback.py             # Playback state machine: play, pause, step, scrub
│   └── hud.py                  # Stats overlay, message log, agent info panel
│
└── tests/
    ├── test_lrta_star.py
    ├── test_messages.py
    ├── test_grid.py
    ├── test_agents.py
    └── test_simulation.py
```

---

## PHASE 1 — Domain Model & Messages

**Files to create:** `domain/cell.py`, `domain/grid.py`, `domain/signal.py`, `domain/reservation.py`, `messages/messages.py`, `config.py`

### `domain/cell.py`

```python
from enum import IntEnum
from dataclasses import dataclass

class CellType(IntEnum):
    FREE = 0
    SIGNAL = 1
    OBSTACLE = 2
    AGENT = 3
    BASE = 4

@dataclass(frozen=True)
class Cell:
    row: int
    col: int

    def manhattan_distance(self, other: "Cell") -> int:
        return abs(self.row - other.row) + abs(self.col - other.col)
```

Note: `Cell` is frozen (hashable) so it can be used as a dict key and in sets. Cell type is NOT stored on the Cell itself — it's tracked in the Grid matrix. This avoids mutability issues when cells are used as keys.

### `domain/grid.py`

- `Grid(rows: int, cols: int)` — creates the cell matrix and a parallel `cell_types: dict[Cell, CellType]` map.
- `get_cell(r, c) → Cell`
- `set_cell_type(cell, CellType)`
- `get_cell_type(cell) → CellType`
- `get_passable_neighbors(cell) → list[Cell]` — returns 4-connected neighbors where type is not `OBSTACLE`. Does NOT exclude `AGENT` cells (that's the Rescue Agent's job during move selection).
- `is_passable(cell) → bool`
- `all_cells() → Iterator[Cell]`

### `domain/signal.py`

```python
@dataclass
class Signal:
    signal_id: int
    location: Cell
    created_at_tick: int
    resolved_at_tick: int | None = None
    resolved_by: int | None = None    # agent_id
```

### `domain/reservation.py`

```python
@dataclass(frozen=True)
class Reservation:
    agent_id: int
    cell: Cell
    tick: int
```

### `messages/messages.py`

Base class and 10 concrete types, all dataclasses:

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class Message:
    sender_id: int
    receiver_id: int      # -1 for broadcast
    msg_type: str
    tick: int
    # Subclasses add their own fields; no generic payload dict.

@dataclass
class AssignMessage(Message):
    target: Cell
    msg_type: str = field(default="ASSIGN", init=False)

@dataclass
class FreeMessage(Message):
    agent_id: int          # redundant with sender_id but explicit per spec
    position: Cell
    msg_type: str = field(default="FREE", init=False)

# ... same pattern for all 10 types:
# NeighborQueryMessage(position: Cell)
# NeighborResponseMessage(neighbors: list[tuple[Cell, CellType, float]])
# MoveMessage(from_cell: Cell, to_cell: Cell)
# HUpdateMessage(cell: Cell, value: float)
# ReserveMessage(cell: Cell, reserve_tick: int)
# ClearedMessage(signal: Cell)
# NewSignalMessage(location: Cell)
# TerminateMessage()  — no extra fields
```

### `config.py`

```python
@dataclass
class SimulationConfig:
    rows: int
    cols: int
    obstacle_coords: list[tuple[int, int]]
    base_location: tuple[int, int]
    initial_signals: list[tuple[int, int]]
    agent_count: int
    dynamic_signal_stream: list[tuple[int, int, int]]  # (row, col, tick)
    max_ticks: int = 1000
    seed: int = 42
```

### Tests for Phase 1

- `test_grid.py`: Create a 5×5 grid with known obstacles. Verify `get_passable_neighbors` at corners, edges, and adjacent to obstacles. Verify `manhattan_distance`.
- `test_messages.py`: Construct each message type, verify `msg_type` field, verify fields are accessible.

---

## PHASE 2 — Agent Base Class & Environment Agent

**Files to create:** `agents/agent.py`, `agents/environment_agent.py`

### `agents/agent.py`

```python
from abc import ABC, abstractmethod
from collections import deque

class Agent(ABC):
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: deque[Message] = deque()

    def send_message(self, receiver: "Agent", message: Message):
        """Post a message directly to another agent's inbox."""
        receiver.inbox.append(message)

    def drain_inbox(self) -> list[Message]:
        """Remove and return all messages from inbox."""
        messages = list(self.inbox)
        self.inbox.clear()
        return messages

    @abstractmethod
    def step(self, tick: int) -> None:
        """Execute one simulation tick."""
        ...
```

No global message bus. Agents hold references to each other (set during `Simulation.setup()`). Broadcasting means iterating over a list of recipients and calling `send_message` on each.

### `agents/environment_agent.py` — EnvironmentAgent

**Constructor args:** `agent_id`, `grid: Grid`, `coordinator: Agent` (reference for sending `NEW_SIGNAL`).

**State:**
- `grid: Grid` — the authoritative grid
- `occupancy_map: dict[Cell, int]` — cell → agent_id, only for cells currently occupied by a rescue agent
- `heuristic_table: dict[Cell, float]` — shared LRTA\* h-values
- `active_signals: dict[int, Signal]` — signal_id → Signal
- `resolved_signals: list[Signal]`

**Initialization (`initialize(signals, base, rescue_agent_positions)`):**
1. Set cell types: obstacles, base, signals, agent starting positions.
2. Initialize `heuristic_table`: for every non-obstacle cell, `h(cell) = min Manhattan distance to any active signal cell`. Signal cells get `h = 0`. If no signals exist yet, set all h-values to 0 (they'll be recomputed when signals arrive).
3. Populate `occupancy_map` with initial agent positions.

**`step(tick)` behavior:**
1. `messages = self.drain_inbox()`
2. Process in this order:
   - `ClearedMessage`: set cell type to `FREE`, move signal to `resolved_signals`.
   - `HUpdateMessage`: write `value` to `heuristic_table[cell]`.
   - `MoveMessage`: `occupancy_map[from_cell]` → delete; `occupancy_map[to_cell] = sender_id`.
   - `NeighborQueryMessage`: for each passable neighbor of `position`, build `(cell, cell_type, h_value)` tuple; send `NeighborResponseMessage` back to sender.

**`inject_dynamic_signal(signal: Signal, tick: int)`** — called by Simulation:
1. `grid.set_cell_type(signal.location, CellType.SIGNAL)`
2. `heuristic_table[signal.location] = 0`
3. `active_signals[signal.signal_id] = signal`
4. Send `NewSignalMessage` to Coordinator.

**Important:** When a signal is cleared, do NOT recalculate all h-values. The LRTA\* convergence property means agents will naturally update h-values as they traverse the grid toward their next targets. Only dynamic signal *injection* sets `h = 0` for the new signal cell.

### Tests for Phase 2

- Create EnvironmentAgent with a 5×5 grid, 2 signals. Verify h-table initialization (signal cells = 0, adjacent cells = 1, etc.).
- Send a `NeighborQueryMessage`, verify the response contains correct neighbors with h-values.
- Send a `MoveMessage`, verify occupancy map updates.
- Send an `HUpdateMessage`, verify h-table is written.

---

## PHASE 3 — LRTA\* Algorithm

**File to create:** `algorithms/lrta_star.py`

This is a **pure function** with no side effects — it takes data in, returns results. All message sending is done by the calling RescueAgent.

```python
def lrta_star_step(
    current_h: float,
    neighbors: list[tuple[Cell, float]],  # (cell, h_value) pairs for passable neighbors
    reserved_cells: set[Cell],            # cells reserved by peers this tick
) -> tuple[float, Cell | None]:
    """
    Returns:
        updated_h: new h-value for the current cell (h(i) ← min_j [1 + h(j)])
        best_move: cell to move to, or None if all neighbors blocked/reserved

    The move cost k(i,j) = 1 for all grid moves (uniform cost).
    """
    if not neighbors:
        return current_h, None

    # Compute f-values
    f_values = [(cell, 1.0 + h) for cell, h in neighbors]

    # h-update: minimum f across ALL neighbors (including reserved ones)
    updated_h = min(f for _, f in f_values)

    # Move selection: exclude reserved cells
    available = [(cell, f) for cell, f in f_values if cell not in reserved_cells]
    if not available:
        return updated_h, None  # all neighbors reserved → wait

    # Break ties by (f-value, row, col) for determinism
    best_move = min(available, key=lambda x: (x[1], x[0].row, x[0].col))[0]
    return updated_h, best_move
```

**Critical detail:** The h-update uses ALL neighbors (including reserved ones) because the heuristic is a property of the cell, not of the agent's available moves. Only the move selection filters out reserved cells.

### Tests for Phase 3

- 3 neighbors with h-values [5, 3, 7], no reservations → `updated_h = 4.0`, `best_move` = neighbor with h=3.
- Same but the h=3 neighbor is reserved → `updated_h = 4.0` (unchanged), `best_move` = neighbor with h=5.
- All neighbors reserved → returns `(updated_h, None)`.
- Single neighbor → `updated_h = 1 + h(neighbor)`, `best_move` = that neighbor.
- Verify h never decreases (monotone property): call repeatedly with decreasing neighbor h-values, assert `updated_h` is non-decreasing.

---

## PHASE 4 — Coordinator Agent

**File to create:** `agents/coordinator_agent.py`

**Constructor args:** `agent_id`, `rescue_agents: list[Agent]` (references for sending `ASSIGN` and `TERMINATE`).

**State:**
- `pending_signals: list[Signal]` — unassigned signals
- `idle_agents: dict[int, Cell]` — agent_id → last known position (from `FREE` message)
- `assignments: dict[int, Signal]` — agent_id → currently assigned signal
- `all_agent_ids: set[int]` — all rescue agent IDs (for termination check)

**`initialize(initial_signals: list[Signal])`:** Populate `pending_signals`.

**`step(tick)` behavior:**
1. `messages = self.drain_inbox()`
2. Process `ClearedMessage` first: remove signal from `pending_signals` (if present) and from `assignments` (find and remove by signal location).
3. Process `NewSignalMessage`: create Signal, add to `pending_signals`. If any agent in `idle_agents`, immediately assign (nearest-first).
4. Process `FreeMessage(agent_id, position)`:
   - Remove from `assignments` if present.
   - If `pending_signals` non-empty: find the signal with minimum `position.manhattan_distance(signal.location)`, remove it from `pending_signals`, send `AssignMessage` to that agent, add to `assignments`.
   - Else: add to `idle_agents`.
5. **Termination check:** if `pending_signals` is empty AND `assignments` is empty AND `len(idle_agents) == len(all_agent_ids)` → broadcast `TerminateMessage` to all rescue agents.

**Assignment ordering:** When an idle agent exists and a new signal arrives, pick the idle agent nearest to the signal. When a free agent arrives and multiple signals exist, pick the signal nearest to the agent. Both use Manhattan distance.

### Tests for Phase 4

- Initialize with 3 signals. Send `FreeMessage` from agent 0 at position (0,0). Verify `ASSIGN` is sent with the nearest signal.
- Send `ClearedMessage` for a signal in the queue. Verify it's removed.
- All signals cleared, all agents free → verify `TERMINATE` is broadcast.
- Dynamic `NewSignalMessage` with idle agent → verify immediate assignment.

---

## PHASE 5 — Rescue Agent

**File to create:** `agents/rescue_agent.py`

**Constructor args:** `agent_id`, `start_position: Cell`, `environment: Agent`, `coordinator: Agent`, `peers: list[Agent]`.

**State:**
- `position: Cell`
- `target: Cell | None`
- `received_reservations: set[Reservation]` — peer reservations for current tick
- `movement_history: list[Cell]`
- `halted: bool`
- `free_sent: bool` — tracks whether FREE was already sent (avoids re-sending every tick while idle)
- `wait_count: int` — ticks spent waiting due to conflicts (for stats)

**`step(tick)` behavior — Sub-phase A (called first):**
1. `messages = self.drain_inbox()`
2. For each message:
   - `AssignMessage` → `self.target = msg.target`; `self.free_sent = False`.
   - `ReserveMessage` → `self.received_reservations.add(Reservation(msg.sender_id, msg.cell, msg.reserve_tick))`.
   - `ClearedMessage` → if `msg.signal == self.target`: clear target. This agent did NOT clear it (a peer did), so send `FreeMessage` to Coordinator.
   - `TerminateMessage` → `self.halted = True`.
3. If halted: return.
4. If at target:
   - Broadcast `ClearedMessage` to all peers + Environment.
   - Send `FreeMessage` to Coordinator.
   - `self.target = None`; `self.free_sent = True`.
   - Return.
5. If no target:
   - If not `self.free_sent`: send `FreeMessage` to Coordinator; `self.free_sent = True`.
   - Return.
6. Send `NeighborQueryMessage` to Environment.

**`step_act(tick)` — Sub-phase B (called after Environment processes queries):**
1. Drain inbox for `NeighborResponseMessage` only.
2. If no response received (edge case): wait this tick, return.
3. Extract neighbor data: `[(cell, h_value) for cell, cell_type, h_value in response.neighbors]`. Filter out obstacle cells (should already be filtered by Environment, but defensive).
4. Build `reserved_cells`: all cells from `self.received_reservations` where `tick` matches current tick.
5. Call `lrta_star_step(current_h, neighbors, reserved_cells)` → `(updated_h, best_move)`.
6. Send `HUpdateMessage(self.position, updated_h)` to Environment.
7. If `best_move is None`: wait, increment `wait_count`, return.
8. **Collision resolution:** Check if any peer's reservation in `received_reservations` targets `best_move`.
   - If conflict: if `self.agent_id < conflicting_agent_id` → wait (lower yields). Else → proceed.
   - If multiple conflicts: yield to ANY higher-priority (lower-id) agent.
9. If proceeding: broadcast `ReserveMessage(best_move, tick)` to all peers. Send `MoveMessage(self.position, best_move)` to Environment. Update `self.position = best_move`. Append to `movement_history`.
10. Clear `received_reservations`.

**Design note on the two-method split:** The Simulation calls `agent.step(tick)` for all rescue agents (sub-phase A), then `environment.step(tick)`, then `agent.step_act(tick)` for all rescue agents (sub-phase B). This gives the Environment time to process queries and send responses before agents act.

### Tests for Phase 5

- Single agent, single signal 3 cells away on an empty grid. Run tick-by-tick. Verify agent reaches target in 3 ticks, sends CLEARED, sends FREE.
- Two agents targeting the same cell from different directions. One arrives first, clears it. Verify the other receives CLEARED and sends FREE.
- Two agents intending to move to the same cell. Verify lower-id waits, higher proceeds.

---

## PHASE 6 — Simulation Engine

**Files to create:** `simulation.py`

### `Simulation(config: SimulationConfig)`

**State:**
- `config: SimulationConfig`
- `environment: EnvironmentAgent`
- `coordinator: CoordinatorAgent`
- `rescue_agents: list[RescueAgent]`
- `tick: int = 0`
- `terminated: bool = False`
- `frames: list[dict]` — one frame per tick for UI replay
- `dynamic_signal_queue: list[tuple[int, int, int]]` — sorted by tick

### `setup()`

1. Create `Grid` from config. Set obstacle cell types. Set base cell type.
2. Create signals from `initial_signals`, assign incrementing IDs.
3. Create `EnvironmentAgent(agent_id=-1, grid, coordinator_ref)`.
4. Create `CoordinatorAgent(agent_id=-2, rescue_agent_refs)`.
5. Create K `RescueAgent` instances, all starting at `base_location`. Agent IDs: 0 through K-1.
6. Wire references: each RescueAgent gets refs to Environment, Coordinator, and peer list. Coordinator gets refs to all RescueAgents. Environment gets ref to Coordinator.
7. Call `environment.initialize(signals, base, agent_positions)`.
8. Call `coordinator.initialize(initial_signals)`.
9. Each RescueAgent sends initial `FreeMessage` to Coordinator (they start unassigned).
10. Sort `dynamic_signal_stream` by tick.

### `advance_tick()`

```
tick += 1

# 1. Inject dynamic signals scheduled for this tick
while dynamic_signal_queue and dynamic_signal_queue[0][2] == tick:
    r, c, _ = dynamic_signal_queue.pop(0)
    signal = Signal(next_signal_id(), Cell(r, c), tick)
    environment.inject_dynamic_signal(signal, tick)

# 2. Coordinator processes messages from previous tick (FREE, CLEARED, NEW_SIGNAL)
coordinator.step(tick)

# 3. Sub-phase A: Rescue Agents send queries + process assignments
for agent in rescue_agents:
    agent.step(tick)

# 4. Environment processes queries and replies
environment.step(tick)

# 5. Sub-phase B: Rescue Agents act (LRTA*, reserve, move)
for agent in rescue_agents:
    agent.step_act(tick)

# 6. Record frame
frames.append(collect_frame(tick))

# 7. Check termination
if all(a.halted for a in rescue_agents):
    terminated = True
if tick >= config.max_ticks:
    terminated = True
```

### `run() → dict`

```python
def run(self) -> dict:
    self.setup()
    while not self.terminated:
        self.advance_tick()
    return self.collect_statistics()
```

### `collect_frame(tick) → dict`

Captures the full state for one tick (used by the Pygame UI for replay):

```python
{
    "tick": int,
    "grid_types": list[list[int]],        # NxM matrix of CellType ordinals
    "agents": [
        {
            "id": int,
            "position": (int, int),
            "target": (int, int) | None,
            "state": "moving" | "waiting" | "idle" | "halted"
        }, ...
    ],
    "heuristic_map": dict[tuple[int,int], float],  # sparse: only cells with h != inf
    "active_signals": list[tuple[int, int]],
    "resolved_signals": list[tuple[int, int]],
    "messages_this_tick": list[dict]       # [{type, sender, receiver, payload}, ...]
}
```

### `collect_statistics() → dict`

```python
{
    "makespan": int,                       # tick of last signal resolved
    "total_steps": int,                    # sum of all agent movements
    "total_ticks": int,
    "signals_resolved": int,
    "per_agent": [
        {
            "id": int,
            "steps": int,
            "signals_resolved": int,
            "wait_ticks": int,
            "trajectory": list[tuple[int,int]]
        }, ...
    ],
    "resolution_log": [
        {"signal": (int,int), "resolved_by": int, "tick": int}, ...
    ]
}
```

### Tests for Phase 6

- **Smoke test:** 5×5 grid, 1 agent, 1 signal, no obstacles. `run()` completes. Signal resolved. Makespan = Manhattan distance.
- **Multi-agent:** 10×10 grid, 3 agents, 5 signals. `run()` completes. All signals resolved. No agent occupies the same cell at the same tick (validate from frames).
- **Dynamic signals:** 8×8 grid, 2 agents, 1 initial signal, 2 dynamic signals at ticks 10 and 20. All 3 resolved.
- **Max ticks safety:** 5×5 grid with unreachable signal (surrounded by obstacles). Simulation terminates at `max_ticks` without hanging.

---

## PHASE 7 — Grid Generator

**File to create:** `utils/grid_generator.py`

```python
def generate_config(
    rows: int = 20,
    cols: int = 20,
    obstacle_density: float = 0.2,   # 0.0 to 0.4
    num_signals: int = 5,
    agent_count: int = 3,
    base_location: tuple[int, int] | None = None,  # None = center
    dynamic_signal_frequency: float = 0.0,          # avg signals per tick (Poisson)
    dynamic_signal_duration: int = 100,              # ticks over which dynamic signals appear
    max_ticks: int = 500,
    seed: int = 42,
) -> SimulationConfig:
```

**Algorithm:**
1. Seed the RNG.
2. Place base (default: center of grid).
3. Randomly place obstacles at the given density, excluding the base cell.
4. BFS flood-fill from base. If any free cell is unreachable, remove the obstacle that blocks it (keep removing until all free cells are reachable).
5. Place initial signals at random free cells (not base, not obstacles). Verify each is reachable from base.
6. Generate dynamic signal stream: for each tick in `[1, dynamic_signal_duration]`, sample `Poisson(dynamic_signal_frequency)` signals at random free cells.
7. Return `SimulationConfig`.

---

## PHASE 8 — Statistics Collector

**File to create:** `utils/stats.py`

A utility that processes the `frames` list and `resolution_log` from the Simulation to produce summary statistics and per-agent breakdowns. The `collect_statistics` method in `simulation.py` delegates to this.

Additional computed metrics beyond the basics:
- **Average resolution time:** mean ticks from signal creation to resolution.
- **Idle ratio per agent:** fraction of ticks spent idle (no target).
- **Conflict count:** total ticks where an agent had to wait due to reservation conflict.
- **Heuristic convergence:** optional — track mean h-value change per tick to show LRTA\* convergence.

---

## PHASE 9 — Pygame UI

**Files to create:** `ui/renderer.py`, `ui/controls.py`, `ui/playback.py`, `ui/hud.py`

**Dependencies:** `pygame`, `pygame_gui`

The UI has two modes:
1. **Configure & Run:** Set parameters via a control panel, generate a grid, run the simulation, then switch to replay.
2. **Replay:** Step through recorded frames with playback controls and overlays.

### `ui/renderer.py` — Grid Renderer

Responsible for drawing the NxM grid onto a Pygame surface.

**Cell rendering (each cell is a `CELL_SIZE × CELL_SIZE` square):**

| CellType | Color | Detail |
|---|---|---|
| `FREE` | `#1a1a2e` (dark navy) | — |
| `OBSTACLE` | `#0f0f0f` (near-black) | Hatched or solid |
| `SIGNAL` (active) | `#e74c3c` (red) | Pulsing glow animation (sine wave alpha) |
| `SIGNAL` (resolved) | `#2ecc71` (green) | Checkmark icon or faded |
| `BASE` | `#3498db` (blue) | House/flag icon |
| `AGENT` | Per-agent color from palette | Filled circle with agent ID text |

**Agent colors:** Use a distinct palette (e.g., `["#e74c3c", "#2ecc71", "#3498db", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22", "#ecf0f1", "#fd79a8", "#00cec9"]`) indexed by agent_id.

**Overlay layers (toggled via keyboard):**
- **`[H]` Heuristic heatmap:** Semi-transparent color overlay per cell, gradient from blue (low h) to red (high h). Normalize to the current frame's min/max h-values.
- **`[T]` Agent trails:** Draw semi-transparent lines connecting each agent's movement history up to the current tick.
- **`[R]` Reservations:** Highlight cells reserved this tick with a yellow border.
- **`[G]` Grid lines:** Toggle grid line visibility.

**Scaling:** `CELL_SIZE` should auto-scale based on window size and grid dimensions: `CELL_SIZE = min(GRID_AREA_WIDTH // cols, GRID_AREA_HEIGHT // rows)`. Minimum 12px, maximum 60px.

### `ui/controls.py` — Configuration Panel

A sidebar (right side, ~280px wide) using `pygame_gui` elements:

| Control | Widget | Range |
|---|---|---|
| Grid rows | `UIHorizontalSlider` + label | 5–50 |
| Grid cols | `UIHorizontalSlider` + label | 5–50 |
| Obstacle density | `UIHorizontalSlider` | 0%–40% |
| Rescue agents (K) | `UIHorizontalSlider` | 1–10 |
| Initial signals | `UIHorizontalSlider` | 1–20 |
| Dynamic signal freq | `UIHorizontalSlider` | 0.0–2.0 |
| Seed | `UITextEntryLine` | int |
| Max ticks | `UITextEntryLine` | int |
| **Generate** | `UIButton` | Generates grid + runs simulation |
| **Reset** | `UIButton` | Clears simulation, returns to config |

After clicking **Generate**, the control panel collapses or grays out, and the playback controls become active.

### `ui/playback.py` — Playback Controls

Bottom bar with:
- **◄◄ (Restart):** Go to tick 0.
- **◄ (Step Back):** Go to previous tick.
- **▶ / ❚❚ (Play/Pause):** Auto-advance ticks at the current speed.
- **► (Step Forward):** Go to next tick.
- **►► (Jump to End):** Go to last tick.
- **Speed slider:** 1–60 ticks per second (maps to Pygame clock delay).
- **Tick scrubber:** Horizontal slider spanning all ticks. Draggable.
- **Tick label:** "Tick 14 / 120"

**Keyboard shortcuts:**
- `Space`: Play/Pause
- `Left/Right arrow`: Step back/forward
- `Home/End`: First/last tick
- `+/-`: Speed up/slow down

### `ui/hud.py` — Heads-Up Display

An overlay panel (top-right corner or togglable sidebar) showing:

**Stats panel (always visible during replay):**
```
Makespan: 47    Total Steps: 123
Signals: 5/8 resolved
Tick: 14 / 120
```

**Agent detail (shown when clicking an agent on the grid):**
```
Agent #2 [color swatch]
Position: (7, 3)
Target: (12, 8)
State: moving
Steps: 34
Signals resolved: 2
```

**Message log (toggleable with `[M]` key):**
A scrollable text area showing messages from the current tick:
```
[T14] Rescue#0 → Environment: NEIGHBOR_QUERY (3,5)
[T14] Environment → Rescue#0: NEIGHBOR_RESPONSE [4 neighbors]
[T14] Rescue#0 → all: RESERVE (3,6)
[T14] Rescue#0 → Environment: MOVE (3,5)→(3,6)
```

### Main Window Layout

```
┌─────────────────────────────────────┬──────────────┐
│                                     │              │
│                                     │   Config /   │
│          Grid Canvas                │   Stats      │
│          (auto-scaled)              │   Panel      │
│                                     │   (280px)    │
│                                     │              │
├─────────────────────────────────────┴──────────────┤
│  ◄◄  ◄  ▶  ►  ►►   [===●=========]  Tick 14/120  │
│  Speed: [====●===]  1-60 tps                       │
├────────────────────────────────────────────────────┤
│  Message Log (collapsible, ~100px height)          │
└────────────────────────────────────────────────────┘
```

**Window size:** Default 1280×800, resizable. Grid area fills available space minus sidebar and bottom bar.

### `main.py` — Entry Point

```python
def main():
    # Option 1: CLI mode (no UI)
    # python main.py --headless --rows 20 --cols 20 --agents 3 --signals 5
    # → runs simulation, prints stats, saves frames.json

    # Option 2: Pygame UI mode (default)
    # python main.py
    # → launches the Pygame window with config panel
```

In UI mode, the flow is:
1. Show config panel. User adjusts sliders.
2. User clicks **Generate**. `grid_generator.generate_config(...)` produces a `SimulationConfig`. `Simulation(config).run()` executes (blocking — show a "Running..." overlay). Frames are stored in memory.
3. Switch to replay mode. User uses playback controls to step through frames.
4. User clicks **Reset** to return to step 1.

---

## Implementation Order & Milestones

| # | Phase | Deliverables | Depends On |
|---|---|---|---|
| 1 | Domain model + messages | `domain/*`, `messages/*`, `config.py`, unit tests | — |
| 2 | Agent base + Environment Agent | `agents/agent.py`, `agents/environment_agent.py`, tests | Phase 1 |
| 3 | LRTA\* algorithm | `algorithms/lrta_star.py`, unit tests | Phase 1 |
| 4 | Coordinator Agent | `agents/coordinator_agent.py`, tests | Phase 2 |
| 5 | Rescue Agent | `agents/rescue_agent.py`, integration tests | Phases 2, 3, 4 |
| 6 | Simulation engine | `simulation.py`, end-to-end tests | Phases 1–5 |
| 7 | Grid generator | `utils/grid_generator.py` | Phase 1 |
| 8 | Statistics | `utils/stats.py` | Phase 6 |
| 9 | Pygame UI | `ui/*`, `main.py` | Phases 6, 7, 8 |

**When implementing each phase, create the files listed and their corresponding tests. Run all tests before proceeding to the next phase. If a test fails, fix the implementation before moving on.**

---

## Key Invariants to Maintain

These must hold true at every tick throughout the simulation. Validate in tests.

1. **No dual occupancy:** At most one rescue agent per cell at any tick (check `occupancy_map` after all moves).
2. **h-monotonicity:** `h(i)` for any cell `i` never decreases across ticks (LRTA\* property).
3. **Signal lifecycle:** Every signal transitions exactly once from active → resolved. A resolved signal is never re-activated.
4. **Assignment consistency:** At any tick, each rescue agent has at most one assignment. Each signal is assigned to at most one agent.
5. **Termination guarantee:** If all signals are reachable from the base, the simulation terminates (all signals resolved) in finite ticks.
6. **Message integrity:** Every message sent is eventually drained by its recipient (no lost messages — guaranteed by deque semantics).

---

## Design Decisions & Tradeoffs

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| Tick model | 2-sub-phase (query → act) | Single-phase with 1-tick query latency | Matches spec's "each tick" LRTA\* loop without wasted ticks |
| Conflict tie-break | Lower agent_id waits | Random, round-robin | Per spec; deterministic and reproducible |
| h-table storage | Centralized in EnvironmentAgent | Per-agent local copies | Per spec (ADP shared memory model) |
| Message delivery | Direct inbox push (deque) | Centralized message bus | Simpler; preserves async semantics via drain-at-start |
| Cell identity | Frozen `Cell(row, col)` as value object | Mutable cell with type field | Hashable for dicts/sets; type tracked separately in Grid |
| UI framework | Pygame + pygame_gui | Tkinter, PyQt, React | Lightweight, 2D-native, good for grid rendering, no browser |
| Simulation-UI coupling | In-memory frames list | JSON file export | Faster for single-process; add JSON export later for headless mode |
