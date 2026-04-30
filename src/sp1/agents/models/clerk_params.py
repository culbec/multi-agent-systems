from __future__ import annotations

from pydantic import ConfigDict, Field

from sp1.agents.models.agent_params import AgentParams
from sp1.infra.blackboard import Blackboard


class ClerkParams(AgentParams):
    """Parameters for the Clerk agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    blackboard: Blackboard = Field(..., description="Shared blackboard instance.")
    editor_jid: str = Field(..., description="JID of the Editor agent.")
    user_id: str = Field(default="default_user", description="Default user identifier for this clerk instance.")
    session_timeout_seconds: int = Field(default=300, description="Seconds before an idle session is timed out.")
