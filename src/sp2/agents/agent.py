from abc import ABC, abstractmethod
from collections import deque
from typing import TYPE_CHECKING

from src.sp2.messages.messages import Message

if TYPE_CHECKING:
    from src.sp2.actions.action import Action
    from src.sp2.environment.environment import Environment
    from src.sp2.perceptions.percept import Percept


class Agent(ABC):
    """An autonomous agent managed by the Simulation.

    The agent does not sense the world itself and does not mutate it: the
    Environment builds its percept (``see: S -> P``) and applies its chosen
    actions (``env: S x A -> S``). The agent only *decides* -- it caches the
    percept in ``see`` and runs its goal methods in ``select_actions`` to choose
    actions. This keeps exactly two true agents (Rescue, Coordinator); the
    Environment is not an agent.
    """

    message_callback = None

    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: deque[Message] = deque()
        self.percept: "Percept | None" = None

    # inter-agent messaging
    def send_message(self, receiver: "Agent", message: Message) -> None:
        """Post a message directly to another agent's inbox."""
        receiver.inbox.append(message)
        if Agent.message_callback is not None:
            Agent.message_callback(message)

    def drain_inbox(self) -> list[Message]:
        """Remove and return all messages from the inbox."""
        messages = list(self.inbox)
        self.inbox.clear()
        return messages

    # the sense -> decide -> act cycle
    def see(self, percept: "Percept") -> None:
        """Receive a percept and cache it; subclasses may also update internal
        state here."""
        self.percept = percept

    @abstractmethod
    def select_actions(self, tick: int) -> "list[Action]":
        """Choose the actions to perform from the cached percept (the I -> A
        function). Runs the agent's ``goal_*`` methods; holds no sensing or
        world-mutation logic."""

    def step(self, env: "Environment", tick: int) -> None:
        """One full cycle, faithful to the example's simulation loop:
        ``get_percept -> see -> select_actions -> update_state``."""
        self.see(env.get_percept(self, tick))
        actions = self.select_actions(tick)
        env.update_state(self, actions, tick)
