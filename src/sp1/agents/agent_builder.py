from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Self, TypeVar

from spade.agent import Agent

from sp1.agents.models.agent_params import AgentParams

A = TypeVar("A", bound=Agent)
P = TypeVar("P", bound=AgentParams)


class AgentBuilder(ABC, Generic[A, P]):
    """Abstract builder for SPADE `Agent` subclasses with shared credential handling."""

    def __init__(self) -> None:
        self._jid: str | None = None
        self._password: str | None = None

    def with_credentials(self, jid: str, password: str) -> Self:
        self._jid = jid
        self._password = password
        return self

    @abstractmethod
    def build(self) -> A:
        """Construct and return the configured agent."""
