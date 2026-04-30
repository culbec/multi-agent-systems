from __future__ import annotations

from sp1.agents.agent_builder import AgentBuilder
from sp1.agents.clerk.clerk import ClerkAgent
from sp1.agents.models.clerk_params import ClerkParams
from sp1.infra.blackboard import Blackboard


class ClerkBuilder(AgentBuilder):
    """Builder for the Clerk agent."""

    def __init__(self) -> None:
        super().__init__()
        self._blackboard: Blackboard | None = None
        self._editor_jid: str | None = None
        self._user_id: str = "default_user"
        self._session_timeout_seconds: int = 300

    def with_blackboard(self, blackboard: Blackboard) -> ClerkBuilder:
        self._blackboard = blackboard
        return self

    def with_editor_jid(self, editor_jid: str) -> ClerkBuilder:
        self._editor_jid = editor_jid
        return self

    def with_user_id(self, user_id: str) -> ClerkBuilder:
        self._user_id = user_id
        return self

    def with_session_timeout(self, seconds: int) -> ClerkBuilder:
        self._session_timeout_seconds = seconds
        return self

    def build(self) -> ClerkAgent:
        params = ClerkParams(
            jid=self._jid,
            password=self._password,
            blackboard=self._blackboard,
            editor_jid=self._editor_jid,
            user_id=self._user_id,
            session_timeout_seconds=self._session_timeout_seconds,
        )
        return ClerkAgent(params)
