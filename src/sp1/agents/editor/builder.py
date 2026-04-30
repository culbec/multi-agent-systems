from __future__ import annotations

from sp1.agents.agent_builder import AgentBuilder
from sp1.agents.editor.editor import EditorAgent
from sp1.agents.models.editor_params import EditorParams
from sp1.infra.blackboard import Blackboard
from sp1.infra.llm_config import LLMConfig


class EditorBuilder(AgentBuilder):
    """Builder for the Editor agent."""

    def __init__(self) -> None:
        super().__init__()
        self._blackboard: Blackboard | None = None
        self._clerk_jid: str | None = None
        self._relevance_weight: float = 0.5
        self._credibility_weight: float = 0.3
        self._novelty_weight: float = 0.2
        self._min_credibility_threshold: float = 0.15
        self._llm_config: LLMConfig = LLMConfig()

    def with_blackboard(self, blackboard: Blackboard) -> EditorBuilder:
        self._blackboard = blackboard
        return self

    def with_clerk_jid(self, clerk_jid: str) -> EditorBuilder:
        self._clerk_jid = clerk_jid
        return self

    def with_weights(self, relevance: float, credibility: float, novelty: float) -> EditorBuilder:
        self._relevance_weight = relevance
        self._credibility_weight = credibility
        self._novelty_weight = novelty
        return self

    def with_min_credibility(self, threshold: float) -> EditorBuilder:
        self._min_credibility_threshold = threshold
        return self

    def with_llm_config(self, config: LLMConfig) -> EditorBuilder:
        self._llm_config = config
        return self

    def build(self) -> EditorAgent:
        params = EditorParams(
            jid=self._jid,
            password=self._password,
            blackboard=self._blackboard,
            clerk_jid=self._clerk_jid,
            relevance_weight=self._relevance_weight,
            credibility_weight=self._credibility_weight,
            novelty_weight=self._novelty_weight,
            min_credibility_threshold=self._min_credibility_threshold,
            llm_config=self._llm_config,
        )
        return EditorAgent(params)
