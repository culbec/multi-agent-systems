from __future__ import annotations

from pydantic import ConfigDict, Field

from sp1.agents.models.agent_params import AgentParams
from sp1.infra.blackboard import Blackboard
from sp1.infra.llm_config import LLMConfig


class EditorParams(AgentParams):
    """Parameters for the Editor agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    blackboard: Blackboard = Field(..., description="Shared blackboard instance.")
    clerk_jid: str = Field(..., description="JID of the Clerk agent.")
    relevance_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    credibility_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    novelty_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    min_credibility_threshold: float = Field(default=0.15, description="Articles below this are flagged/demoted.")
    llm_config: LLMConfig = Field(default_factory=LLMConfig)
