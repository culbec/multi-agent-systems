from __future__ import annotations

from pydantic import ConfigDict, Field

from sp1.agents.models.agent_params import AgentParams
from sp1.infra.blackboard import Blackboard


class AnalystParams(AgentParams):
    """Base parameters shared by all Analyst agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    blackboard: Blackboard = Field(..., description="Shared blackboard instance.")
    editor_jid: str = Field(..., description="JID of the Editor agent.")
    dimension: str = Field(..., description="Scoring dimension produced by this analyst.")
    poll_interval_seconds: int = Field(default=30, ge=1, description="How often to check for new articles to score.")
