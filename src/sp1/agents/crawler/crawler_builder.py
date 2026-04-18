from __future__ import annotations

import newspaper

from sp1.agents.agent_builder import AgentBuilder
from sp1.agents.crawler.constants import POLL_INTERVAL_SEC
from sp1.agents.crawler.crawler import CrawlerAgent
from sp1.agents.crawler.models.crawler_params import CrawlerParams
from sp1.infra.blackboard import Blackboard


class CrawlerBuilder(AgentBuilder[CrawlerAgent, CrawlerParams]):
    def __init__(self) -> None:
        super().__init__()
        self._source_id: str | None = None
        self._rss_url: str | None = None

        self._newspaper_config: newspaper.Config | None = None
        self._poll_interval_seconds: int = POLL_INTERVAL_SEC

        self._blackboard: Blackboard | None = None
        self._editor_jid: str | None = None

    def with_source(self, source_id: str, rss_url: str) -> CrawlerBuilder:
        self._source_id = source_id
        self._rss_url = rss_url
        return self

    def with_blackboard(self, blackboard: Blackboard) -> CrawlerBuilder:
        self._blackboard = blackboard
        return self

    def with_editor_jid(self, editor_jid: str) -> CrawlerBuilder:
        self._editor_jid = editor_jid
        return self

    def with_newspaper_config(self, config: newspaper.Config) -> CrawlerBuilder:
        self._newspaper_config = config
        return self

    def with_poll_interval_seconds(self, seconds: int) -> CrawlerBuilder:
        self._poll_interval_seconds = seconds
        return self

    def build(self) -> CrawlerAgent:
        params = CrawlerParams(
            jid=self._jid,
            password=self._password,
            source_id=self._source_id,
            rss_url=self._rss_url,
            blackboard=self._blackboard,
            editor_jid=self._editor_jid,
            newspaper_config=self._newspaper_config,
            poll_interval_seconds=self._poll_interval_seconds,
        )
        return CrawlerAgent(params)
