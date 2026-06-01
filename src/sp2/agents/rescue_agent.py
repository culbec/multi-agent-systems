from typing import TYPE_CHECKING

from src.sp2.actions.actions import (
    ClearSignalAction,
    MoveAction,
    ReportFreeAction,
    ReserveAction,
    UpdateHeuristicAction,
    WaitAction,
)
from src.sp2.agents.agent import Agent
from src.sp2.algorithms.lrta_star import lrta_star_step
from src.sp2.domain.cell import Cell
from src.sp2.messages.messages import (
    AssignMessage,
    ClearedMessage,
    Message,
    TerminateMessage,
)

if TYPE_CHECKING:  # pragma: no cover
    from src.sp2.actions.action import Action


class RescueAgent(Agent):
    """A rescue agent. It navigates to assigned signals with LRTA*, clears them,
    reports availability, and avoids colliding with peers.

    It holds only beliefs/goals/memory -- ``target``, the learned ``current_h``,
    its movement trail, and the ``halted``/``free_sent``/``wait_count`` flags.
    Its physical position is world state, read from the percept each tick.
    """

    def __init__(self, agent_id: int, start_position: Cell, coordinator: Agent, peers: list[Agent]):
        super().__init__(agent_id)
        self.target: Cell | None = None
        self.current_h: float | None = None
        self.movement_history: list[Cell] = [start_position]
        self.halted = False
        self.free_sent = False
        self.wait_count = 0
        self.coordinator = coordinator
        self.peers = peers

    # ------------------------------------------------------------------ #
    # Perception focusing: report the destination implied by the agent's
    # current orders *plus* any just-received in this tick's messages, so the
    # Environment can focus the neighbourhood sensor on the right target.
    # ------------------------------------------------------------------ #
    def intended_destination(self, messages: tuple[Message, ...], base: Cell | None) -> Cell | None:
        target = self.target
        halted = self.halted
        for msg in messages:
            if isinstance(msg, TerminateMessage):
                halted = True
            elif isinstance(msg, AssignMessage):
                target = msg.target
            elif isinstance(msg, ClearedMessage) and target is not None and msg.signal == target:
                target = None
        if halted:
            return None
        return target if target is not None else base

    # ------------------------------------------------------------------ #
    # Decision: run goals in precedence order, concatenating their actions.
    # ------------------------------------------------------------------ #
    def select_actions(self, tick: int) -> "list[Action]":
        percept = self.percept
        actions: "list[Action]" = []

        actions += self.goal_handle_inbox(percept.messages)
        if self.halted:
            return actions

        arrival = self.goal_clear_on_arrival(tick)
        if arrival:
            return actions + arrival

        actions += self.goal_report_availability()
        actions += self.goal_navigate(tick)
        return actions

    # ------------------------------------------------------------------ #
    # Goals (no sensing, no world mutation -- they only return Actions).
    # ------------------------------------------------------------------ #
    def goal_handle_inbox(self, messages: tuple[Message, ...]) -> "list[Action]":
        actions: "list[Action]" = []
        for msg in messages:
            if isinstance(msg, AssignMessage):
                self.target = msg.target
                self.free_sent = False
                self.current_h = None
            elif isinstance(msg, ClearedMessage):
                if self.target is not None and msg.signal == self.target:
                    self.target = None
                    self.current_h = None
                    self.free_sent = True
                    actions.append(ReportFreeAction(self.percept.position))
            elif isinstance(msg, TerminateMessage):
                self.halted = True
        return actions

    def goal_clear_on_arrival(self, tick: int) -> "list[Action]":
        percept = self.percept
        if self.target is not None and percept.position == self.target:
            actions = [ClearSignalAction(self.target, tick), ReportFreeAction(percept.position)]
            self.target = None
            self.current_h = None
            self.free_sent = True
            return actions
        return []

    def goal_report_availability(self) -> "list[Action]":
        if self.target is None and not self.free_sent:
            self.free_sent = True
            return [ReportFreeAction(self.percept.position)]
        return []

    def goal_navigate(self, tick: int) -> "list[Action]":
        percept = self.percept
        destination = percept.destination
        if destination is None or percept.position is None or percept.position == destination:
            return []
        if not percept.neighbors:
            return [WaitAction()]

        # Seed current_h from the table value (not Manhattan), so the learned,
        # monotone estimate is never reset below the stored value.
        if self.current_h is None:
            self.current_h = (
                percept.position_h
                if percept.position_h is not None
                else float(percept.position.manhattan_distance(destination))
            )

        neighbors = list(percept.neighbors)
        updated_h, best_move = lrta_star_step(self.current_h, neighbors, set(percept.reserved_cells))
        actions: "list[Action]" = [UpdateHeuristicAction(percept.position, destination, updated_h)]

        if best_move is None:
            actions.append(WaitAction())
            return actions

        best_move_h = next((h for cell, h in neighbors if cell == best_move), 0.0)
        actions.append(ReserveAction(best_move, tick))
        actions.append(MoveAction(percept.position, best_move, best_move_h))
        return actions