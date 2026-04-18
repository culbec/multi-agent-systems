from __future__ import annotations

import newspaper
from pydantic import ConfigDict, Field

from sp1.agents.models.agent_params import AgentParams
from sp1.infra.blackboard import Blackboard


class CrawlerParams(AgentParams):
    """SPADE credentials plus crawler-specific settings (validated on construction)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_id: str = Field(
        ...,
        description="Stable identifier for the RSS source (e.g. feed name).",
    )
    rss_url: str = Field(
        ...,
        description="URL of the RSS or Atom feed to poll.",
    )
    blackboard: Blackboard = Field(
        ...,
        description="Shared blackboard for articles and source health.",
    )
    editor_jid: str = Field(
        ...,
        description="JID of the editor agent to notify about source health.",
        pattern=r"[^@]+@[^@]+",
    )
    newspaper_config: newspaper.Config | None = Field(
        default=None,
        description="Optional newspaper4k Config; default applies USER_AGENT from constants.",
    )
    poll_interval_seconds: int = Field(
        default=600,
        ge=1,
        description="Interval in seconds between periodic RSS polls.",
    )
