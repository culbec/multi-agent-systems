import asyncio
import json
from unittest.mock import MagicMock, patch

from spade.agent import BehaviourType

from sp1.agents.crawler.constants import MAX_ARTICLES_PER_CRAWL
from sp1.agents.crawler.crawler import CrawlerAgent
from sp1.agents.crawler.models.crawler_outcome import ArticlesOutcome, SourceUnavailableOutcome
from sp1.tests.agents.crawler.support import (
    MOCK_BOZO_RSS_XML,
    MOCK_EMPTY_RSS_XML,
    MOCK_RSS_XML,
    MockArticle,
    MockBlackboard,
    build_crawler,
    run_handle_crawl_outcome,
)


def test_schema_normalization(
    crawler: CrawlerAgent, mock_blackboard: MockBlackboard, mock_behaviour: MagicMock
) -> None:
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (MOCK_RSS_XML, 200, None)
        with patch("newspaper.Article", MockArticle):
            outcome = crawler.crawl()
            assert isinstance(outcome, ArticlesOutcome)
            articles = outcome.articles
            assert len(articles) == 1

            art = articles[0]
            dumped = art.model_dump()
            assert "article_id" in dumped
            assert dumped["source_id"] == "mock_source"
            assert dumped["title"] == "Article 1"
            assert dumped["body"] == "Body of http://example.com/1"
            assert dumped["summary"] == "Summary 1"
            assert dumped["url"] == "http://example.com/1"
            assert "fetched_at" in dumped
            assert dumped["author"] == "John Doe"
            assert "Technology" in dumped["categories"]
            assert "embedding" in dumped

            run_handle_crawl_outcome(crawler, outcome, mock_behaviour)
            assert len(mock_blackboard.added_batches) == 1
            assert len(mock_blackboard.added_batches[0]) == 1
            assert mock_blackboard.added_batches[0][0]["url"] == "http://example.com/1"
            assert mock_blackboard.health_calls[-1] == ("mock_source", "healthy", "")
            mock_behaviour.send.assert_not_awaited()


def test_deduplication(crawler: CrawlerAgent, mock_blackboard: MockBlackboard, mock_behaviour: MagicMock) -> None:
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (MOCK_RSS_XML, 200, None)
        with patch("newspaper.Article", MockArticle):
            outcome1 = crawler.crawl()
            assert isinstance(outcome1, ArticlesOutcome)
            assert len(outcome1.articles) == 1
            run_handle_crawl_outcome(crawler, outcome1, mock_behaviour)

            outcome2 = crawler.crawl()
            assert isinstance(outcome2, ArticlesOutcome)
            assert len(outcome2.articles) == 0
            run_handle_crawl_outcome(crawler, outcome2, mock_behaviour)

    assert sum(len(batch) for batch in mock_blackboard.added_batches) == 1


def test_error_handling_unavailable(
    crawler: CrawlerAgent, mock_blackboard: MockBlackboard, mock_behaviour: MagicMock
) -> None:
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.side_effect = Exception("Connection error")
        outcome = crawler.crawl()

        assert isinstance(outcome, SourceUnavailableOutcome)
        run_handle_crawl_outcome(crawler, outcome, mock_behaviour)

    assert mock_blackboard.health_calls[-1][0] == "mock_source"
    assert mock_blackboard.health_calls[-1][1] == "unavailable"
    mock_behaviour.send.assert_awaited_once()
    msg = mock_behaviour.send.await_args.args[0]
    assert msg.get_metadata("performative") == "inform"
    payload = json.loads(msg.body)
    assert payload["type"] == "source_health"
    assert payload["status"] == "unavailable"
    assert payload["source_id"] == "mock_source"
    assert "reason" in payload


def test_error_handling_bozo(
    crawler: CrawlerAgent, mock_blackboard: MockBlackboard, mock_behaviour: MagicMock
) -> None:
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (MOCK_BOZO_RSS_XML, 200, None)
        outcome = crawler.crawl()

        assert isinstance(outcome, SourceUnavailableOutcome)
        assert len(outcome.reason) > 0
        run_handle_crawl_outcome(crawler, outcome, mock_behaviour)

    assert mock_blackboard.health_calls[-1][1] == "unavailable"
    mock_behaviour.send.assert_awaited_once()
    msg = mock_behaviour.send.await_args.args[0]
    assert json.loads(msg.body)["status"] == "unavailable"


def test_empty_feed(crawler: CrawlerAgent, mock_blackboard: MockBlackboard, mock_behaviour: MagicMock) -> None:
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (MOCK_EMPTY_RSS_XML, 200, None)
        outcome = crawler.crawl()

        assert isinstance(outcome, ArticlesOutcome)
        assert len(outcome.articles) == 0
        run_handle_crawl_outcome(crawler, outcome, mock_behaviour)

    assert mock_blackboard.added_batches == []
    assert mock_blackboard.health_calls[-1] == ("mock_source", "healthy", "")
    mock_behaviour.send.assert_not_awaited()


def test_health_recovery_sends_inform(crawler: CrawlerAgent, mock_behaviour: MagicMock) -> None:
    """After unavailable, a successful crawl notifies Editor of recovery."""
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.side_effect = [Exception("fail"), (MOCK_RSS_XML, 200, None)]
        bad = crawler.crawl()
        assert isinstance(bad, SourceUnavailableOutcome)
        run_handle_crawl_outcome(crawler, bad, mock_behaviour)
        mock_behaviour.send.reset_mock()

        with patch("newspaper.Article", MockArticle):
            good = crawler.crawl()
        assert isinstance(good, ArticlesOutcome)
        run_handle_crawl_outcome(crawler, good, mock_behaviour)

    mock_behaviour.send.assert_awaited_once()
    msg = mock_behaviour.send.await_args.args[0]
    payload = json.loads(msg.body)
    assert payload["status"] == "healthy"
    assert payload["type"] == "source_health"


def test_bozo_feed_returns_unavailable_not_articles_with_zero_items(crawler: CrawlerAgent) -> None:
    """Invalid XML with bozo and no entries must be source_unavailable, not empty articles."""
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (MOCK_BOZO_RSS_XML, 200, None)
        outcome = crawler.crawl()
    assert isinstance(outcome, SourceUnavailableOutcome)


def test_max_articles_per_crawl() -> None:
    n = MAX_ARTICLES_PER_CRAWL + 5
    items_xml = "\n".join(
        f""" <item>
  <title>Article {i}</title>
  <link>http://example.com/{i}</link>
  <description>Summary {i}</description>
 </item>"""
        for i in range(n)
    )
    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Mock RSS Feed</title>
{items_xml}
</channel>
</rss>
"""
    crawler = build_crawler(MockBlackboard())
    with patch("sp1.agents.crawler.crawler.network.get_html_status") as mock_get_html:
        mock_get_html.return_value = (rss, 200, None)
        with patch("newspaper.Article", MockArticle):
            outcome = crawler.crawl()
    assert isinstance(outcome, ArticlesOutcome)
    assert len(outcome.articles) == MAX_ARTICLES_PER_CRAWL


def test_setup_registers_only_poll_behaviour() -> None:
    async def _run() -> None:
        crawler = build_crawler(MockBlackboard())
        added: list = []
        real_add = type(crawler).add_behaviour

        def capture(behaviour: BehaviourType) -> None:
            added.append(behaviour)
            return real_add(crawler, behaviour)

        crawler.add_behaviour = capture  # type: ignore[method-assign]
        await crawler.setup()
        assert len(added) == 1
        assert isinstance(added[0], CrawlerAgent.PollFeedBehaviour)
        assert not any(isinstance(b, CrawlerAgent.RSSFetchBehaviour) for b in added)

    asyncio.run(_run())
