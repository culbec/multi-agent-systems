from __future__ import annotations

from sp1.agents.agent_builder import AgentBuilder
from sp1.agents.analysts.credibility_analyst import CredibilityAnalystAgent
from sp1.agents.analysts.novelty_analyst import NoveltyAnalystAgent
from sp1.agents.analysts.relevance_analyst import RelevanceAnalystAgent
from sp1.agents.models.analyst_params import AnalystParams
from sp1.infra.blackboard import Blackboard


class AnalystBuilder(AgentBuilder):
    """Builder for Analyst agents (Relevance, Credibility, Novelty)."""

    def __init__(self, dimension: str) -> None:
        super().__init__()
        self._dimension = dimension
        self._blackboard: Blackboard | None = None
        self._editor_jid: str | None = None
        self._poll_interval_seconds: int = 30

    def with_blackboard(self, blackboard: Blackboard) -> AnalystBuilder:
        self._blackboard = blackboard
        return self

    def with_editor_jid(self, editor_jid: str) -> AnalystBuilder:
        self._editor_jid = editor_jid
        return self

    def with_poll_interval_seconds(self, seconds: int) -> AnalystBuilder:
        self._poll_interval_seconds = seconds
        return self

    def build(self) -> RelevanceAnalystAgent | CredibilityAnalystAgent | NoveltyAnalystAgent:
        params = AnalystParams(
            jid=self._jid,
            password=self._password,
            blackboard=self._blackboard,
            editor_jid=self._editor_jid,
            dimension=self._dimension,
            poll_interval_seconds=self._poll_interval_seconds,
        )

        if self._dimension == "relevance":
            return RelevanceAnalystAgent(params)
        if self._dimension == "credibility":
            return CredibilityAnalystAgent(params)
        if self._dimension == "novelty":
            return NoveltyAnalystAgent(params)

        raise ValueError(f"Unknown analyst dimension: {self._dimension}")
