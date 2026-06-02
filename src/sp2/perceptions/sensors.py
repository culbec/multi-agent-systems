from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.sp2.domain.cell import Cell
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import Message

if TYPE_CHECKING:  # pragma: no cover
    from src.sp2.environment.environment import Environment


class Perception(ABC):
    """A sensor: it reads the world (through Environment accessors) plus the
    perceiving agent's vantage and returns one slice of a :class:`Percept`.

    Control is inverted into these classes per the AIMA ``see: S -> P`` seam:
    the Environment owns the sensor instances and composes their output in
    ``get_percept``. Sensors never mutate the world; they only read it (the
    inbox sensor additionally drains the agent's own buffer, and the
    new-signal sensor advances the agent's "known" set -- both are the agent's
    perceptual bookkeeping, not world mutation).
    """

    @abstractmethod
    def sense(self, env: "Environment", agent, tick: int):
        ...


class InboxSensor(Perception):
    """Drains the agent's inbox of surviving inter-agent messages."""

    def sense(self, env: "Environment", agent, tick: int) -> tuple[Message, ...]:
        return tuple(agent.drain_inbox())


class NeighborSensor(Perception):
    """Assembles the passable neighbourhood around the agent, attaching the
    heuristic to ``destination`` for each cell and filtering out cells held by
    idle peers parked at base (they act as permanent obstacles).

    ``destination`` is supplied by the Environment after the inbox is read, so
    a freshly-assigned agent's neighbourhood is focused on the new target in the
    same tick (analogous to the vacuum percept being focused by ``agentDir``).
    """

    def sense(self, env: "Environment", agent, tick: int, destination: Cell | None = None):
        position = env.position_of(agent.agent_id)
        if destination is None:
            destination = agent.target if agent.target is not None else env.base
        if destination is None or position is None or position == destination:
            return ()

        idle_peer_cells = self._idle_peer_cells(env, agent)
        neighbors = []
        for neighbor in env.passable_neighbors(position):
            if neighbor in idle_peer_cells:
                continue
            neighbors.append((neighbor, env.heuristic(neighbor, destination)))
        return tuple(neighbors)

    @staticmethod
    def _idle_peer_cells(env: "Environment", agent) -> set[Cell]:
        cells: set[Cell] = set()
        for peer in getattr(agent, "peers", []):
            if peer.target is None and not getattr(peer, "halted", False):
                peer_cell = env.position_of(peer.agent_id)
                if peer_cell is not None and peer_cell == env.base:
                    cells.add(peer_cell)
        return cells


class ReservationSensor(Perception):
    """The cells the agent must not move into this tick: cells already reserved
    in the Environment's reservation table (Decision D1, Option A) unioned with
    the current cells of still-moving peers (prevents head-on swaps)."""

    def sense(self, env: "Environment", agent, tick: int) -> frozenset[Cell]:
        reserved = set(env.reservations(tick))
        for peer in getattr(agent, "peers", []):
            if getattr(peer, "halted", False):
                continue
            peer_cell = env.position_of(peer.agent_id)
            if peer_cell is None:
                continue
            peer_dest = peer.target if peer.target is not None else env.base
            if peer_dest is not None and peer_cell != peer_dest:
                reserved.add(peer_cell)
        return frozenset(reserved)


class NewSignalSensor(Perception):
    """Diffs the world's active signals against the coordinator's known set,
    returning the signals that have newly appeared and advancing the known set
    (Decision D2 -- replaces the old NEW_SIGNAL message)."""

    def sense(self, env: "Environment", agent, tick: int) -> tuple[Signal, ...]:
        active = env.active_signals_view()
        known = agent.known_signal_ids
        new = tuple(sig for signal_id, sig in active.items() if signal_id not in known)
        for sig in new:
            known.add(sig.signal_id)
        return new