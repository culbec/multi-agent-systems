import asyncio
from unittest.mock import MagicMock

from sp1.agents.crawler import CrawlerAgent, CrawlerBuilder
from sp1.agents.crawler.models.crawler_outcome import CrawlerOutcome
from sp1.infra.blackboard import Blackboard

MOCK_RSS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Mock RSS Feed</title>
 <item>
  <title>Article 1</title>
  <link>http://example.com/1</link>
  <description>Summary 1</description>
  <author>John Doe</author>
  <category>Technology</category>
  <pubDate>Fri, 17 Apr 2026 12:00:00 GMT</pubDate>
 </item>
</channel>
</rss>
"""

MOCK_EMPTY_RSS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Mock Empty RSS Feed</title>
</channel>
</rss>
"""

MOCK_BOZO_RSS_XML = "this is not xml"


class MockArticle:
    def __init__(self, url: str, config: dict | None = None, title: str = "") -> None:
        self.url = url
        self.config = config
        self.title = title
        self.text = f"Body of {url}"
        self.authors = ["Jane Smith"]
        self.publish_date = None

    def download(self) -> None:
        pass

    def parse(self) -> None:
        pass

    def is_valid_body(self) -> bool:
        return True

    def to_json(self, as_string: bool = False) -> None:
        pass


class MockBlackboard(Blackboard):
    """Records blackboard calls for assertions (subclass so `CrawlerParams` validation accepts it)."""

    def __init__(self) -> None:
        super().__init__()
        self.added_batches: list[list[dict]] = []
        self.health_calls: list[tuple[str, str, str]] = []

    async def add_articles(self, articles: list) -> None:
        self.added_batches.append(list(articles))
        await super().add_articles(articles)

    async def update_source_health(self, source_id: str, status: str, reason: str = "") -> None:
        self.health_calls.append((source_id, status, reason))
        await super().update_source_health(source_id, status, reason)


def run_handle_crawl_outcome(crawler: CrawlerAgent, outcome: CrawlerOutcome, mock_behaviour: MagicMock) -> None:
    async def _go() -> None:
        await crawler._handle_crawl_outcome(outcome, mock_behaviour)

    asyncio.run(_go())


def build_crawler(mock_blackboard: MockBlackboard) -> CrawlerAgent:
    return (
        CrawlerBuilder()
        .with_credentials(jid="test@localhost", password="password123")  # noqa: S106
        .with_source(source_id="mock_source", rss_url="http://example.com/rss")
        .with_blackboard(mock_blackboard)
        .with_editor_jid("editor@localhost")
        .with_poll_interval_seconds(60)
        .build()
    )
