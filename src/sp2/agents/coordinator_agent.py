from src.sp2.agents.agent import Agent
from src.sp2.domain.cell import Cell
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    FreeMessage,
    NewSignalMessage,
    TerminateMessage,
)


class CoordinatorAgent(Agent):
    def __init__(self, agent_id: int, rescue_agents: list[Agent]):
        super().__init__(agent_id)
        self.rescue_agents = rescue_agents
        self.agent_registry = {a.agent_id: a for a in rescue_agents}

        self.pending_signals: list[Signal] = []
        self.idle_agents: dict[int, Cell] = {}  # agent_id -> position
        self.assignments: dict[int, Signal] = {}  # agent_id -> Signal
        self.next_signal_id = 1

    def initialize(self, initial_signals: list[Signal]) -> None:
        """Initialize coordinator with initial signals."""
        self.pending_signals = list(initial_signals)
        self.idle_agents.clear()
        self.assignments.clear()
        if initial_signals:
            self.next_signal_id = max(sig.signal_id for sig in initial_signals) + 1
        else:
            self.next_signal_id = 1

    def get_next_signal_id(self) -> int:
        val = self.next_signal_id
        self.next_signal_id += 1
        return val

    def step(self, tick: int) -> None:
        """Execute coordinator step."""
        messages = self.drain_inbox()

        # 1. Process ClearedMessage first
        cleared_msgs = [m for msg in messages if isinstance(msg, ClearedMessage) for m in [msg]]
        for msg in cleared_msgs:
            self.pending_signals = [sig for sig in self.pending_signals if sig.location != msg.signal]
            # Remove from assignments
            for aid, sig in list(self.assignments.items()):
                if sig.location == msg.signal:
                    del self.assignments[aid]

        # 2. Process NewSignalMessage
        new_signal_msgs = [m for msg in messages if isinstance(msg, NewSignalMessage) for m in [msg]]
        for msg in new_signal_msgs:
            new_sig = Signal(signal_id=self.get_next_signal_id(), location=msg.location, created_at_tick=msg.tick)
            self.pending_signals.append(new_sig)

            # If any agent in idle_agents, immediately assign (nearest-first)
            if self.idle_agents:
                best_aid = min(
                    self.idle_agents.keys(), key=lambda aid: self.idle_agents[aid].manhattan_distance(new_sig.location)
                )
                self.pending_signals.remove(new_sig)
                self.assignments[best_aid] = new_sig
                del self.idle_agents[best_aid]

                assign_msg = AssignMessage(
                    sender_id=self.agent_id, receiver_id=best_aid, tick=tick, target=new_sig.location
                )
                self.send_message(self.agent_registry[best_aid], assign_msg)

        # 3. Process FreeMessage
        free_msgs = [m for msg in messages if isinstance(msg, FreeMessage) for m in [msg]]
        for msg in free_msgs:
            aid = msg.agent_id
            pos = msg.position

            if aid in self.assignments:
                del self.assignments[aid]
            if aid in self.idle_agents:
                del self.idle_agents[aid]

            if self.pending_signals:
                # Find signal nearest to agent's position
                best_sig = min(self.pending_signals, key=lambda sig: pos.manhattan_distance(sig.location))
                self.pending_signals.remove(best_sig)
                self.assignments[aid] = best_sig

                assign_msg = AssignMessage(
                    sender_id=self.agent_id, receiver_id=aid, tick=tick, target=best_sig.location
                )
                self.send_message(self.agent_registry[aid], assign_msg)
            else:
                self.idle_agents[aid] = pos

        # 4. Termination check
        if (
            getattr(self, "no_more_dynamic_signals", True)
            and not self.pending_signals
            and not self.assignments
            and len(self.idle_agents) == len(self.agent_registry.keys())
        ):
            for agent in self.rescue_agents:
                term_msg = TerminateMessage(sender_id=self.agent_id, receiver_id=agent.agent_id, tick=tick)
                self.send_message(agent, term_msg)
