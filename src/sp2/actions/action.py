from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from src.sp2.agents.agent import Agent
    from src.sp2.environment.environment import Environment


class Action(ABC):
    """Something an agent can do. Each kind of effect is its own subclass.

    Mirrors the AIMA ``Action``: ``execute`` implements the effect of the agent
    performing the action (the ``env: S x A -> S`` function, applied through the
    Environment's guarded primitives). There is no central dispatcher -- each
    action applies itself when the Environment's ``update_state`` iterates them.
    """

    @abstractmethod
    def execute(self, env: "Environment", agent: "Agent", tick: int) -> None:
        ...

    @abstractmethod
    def __str__(self) -> str:  # pragma: no cover - debugging aid
        ...


class EnvironmentAction(Action):
    """An action whose effect lands on the world State (through the
    Environment's guarded mutators) and, where relevant, on the acting agent's
    own memory."""


class CommunicativeAction(Action):
    """An action whose effect is sending a surviving inter-agent message via
    ``agent.send_message`` (so the UI message log still observes it)."""