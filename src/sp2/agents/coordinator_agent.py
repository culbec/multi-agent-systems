from typing import TYPE_CHECKING

from src.sp2.actions.actions import AssignAction, TerminateAction
from src.sp2.agents.agent import Agent
from src.sp2.domain.cell import Cell
from src.sp2.domain.signal import Signal
from src.sp2.messages.messages import ClearedMessage, FreeMessage, Message

if TYPE_CHECKING:
    from src.sp2.actions.action import Action


class CoordinatorAgent(Agent):
    """The coordinator. It assigns signals to available rescue agents nearest
    first, retires resolved signals, re-assigns freed agents, and halts the team
    when all work is done. It perceives new signals by diffing the world's
    active signals (Decision D2) -- it is no longer told about them."""

    def __init__(self, agent_id: int, rescue_agents: list[Agent]):
        super().__init__(agent_id)
        self.rescue_agents = rescue_agents
        self.agent_registry = {a.agent_id: a for a in rescue_agents}

        self.pending_signals: list[Signal] = []
        self.idle_agents: dict[int, Cell] = {}  # agent_id -> position cell
        self.assignments: dict[int, Signal] = {}  # agent_id -> Signal
        self.known_signal_ids: set[int] = set()  # for the new-signal diff (D2)
        self.no_more_dynamic_signals = True

    def initialize(self, initial_signals: list[Signal]) -> None:
        self.pending_signals = list(initial_signals)
        self.idle_agents.clear()
        self.assignments.clear()
        # Seed known ids from the initial signals so they are not re-flagged new.
        self.known_signal_ids = {sig.signal_id for sig in initial_signals}

    # Decision
    def select_actions(self, tick: int) -> "list[Action]":
        percept = self.percept
        actions: "list[Action]" = []
        actions += self.goal_retire_cleared(percept.messages)
        actions += self.goal_enqueue_new(percept.new_signals)
        actions += self.goal_reassign_free(percept.messages)
        actions += self.goal_detect_termination()
        return actions

    # Goals
    def goal_retire_cleared(self, messages: tuple[Message, ...]) -> "list[Action]":
        for msg in messages:
            if isinstance(msg, ClearedMessage):
                self.pending_signals = [sig for sig in self.pending_signals if sig.location != msg.signal]
                for aid, sig in list(self.assignments.items()):
                    if sig.location == msg.signal:
                        del self.assignments[aid]
        return []

    def goal_enqueue_new(self, new_signals: tuple[Signal, ...]) -> "list[Action]":
        actions: "list[Action]" = []
        for sig in new_signals:
            self.pending_signals.append(sig)
            if self.idle_agents:
                actions += self.goal_assign_nearest_idle(sig)
        return actions

    def goal_assign_nearest_idle(self, signal: Signal) -> "list[Action]":
        best_aid = min(
            self.idle_agents, key=lambda aid: self.idle_agents[aid].manhattan_distance(signal.location)
        )
        self.pending_signals.remove(signal)
        self.assignments[best_aid] = signal
        del self.idle_agents[best_aid]
        return [AssignAction(best_aid, signal.location)]

    def goal_reassign_free(self, messages: tuple[Message, ...]) -> "list[Action]":
        actions: "list[Action]" = []
        for msg in messages:
            if not isinstance(msg, FreeMessage):
                continue
            aid = msg.agent_id
            pos = msg.position
            self.assignments.pop(aid, None)
            self.idle_agents.pop(aid, None)
            if self.pending_signals:
                best_sig = min(self.pending_signals, key=lambda sig: pos.manhattan_distance(sig.location))
                self.pending_signals.remove(best_sig)
                self.assignments[aid] = best_sig
                actions.append(AssignAction(aid, best_sig.location))
            else:
                self.idle_agents[aid] = pos
        return actions

    def goal_detect_termination(self) -> "list[Action]":
        if (
            self.no_more_dynamic_signals
            and not self.pending_signals
            and not self.assignments
            and len(self.idle_agents) == len(self.agent_registry)
        ):
            return [TerminateAction()]
        return []
