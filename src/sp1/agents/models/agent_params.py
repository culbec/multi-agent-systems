import os
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentParams(BaseModel):
    jid: str = Field(
        ...,
        title="Jabber ID",
        description="The assigned Jabber ID for the Agent used to communicate within the MAS.",
        default_factory=lambda: f"agent-{uuid4().hex}@{os.environ.get('SPADE_SERVER', 'localhost')}",
        pattern=r"[^@]+@[^@]+",
    )
    password: str = Field(
        ...,
        description="XMPP password for authenticating this agent.",
    )
