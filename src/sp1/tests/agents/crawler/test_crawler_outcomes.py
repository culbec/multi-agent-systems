import json

from sp1.agents.crawler.models.crawler_article import NormalizedArticleModel
from sp1.agents.crawler.models.crawler_outcome import (
    ArticlesOutcome,
    SourceHealthPayload,
    SourceUnavailableOutcome,
)


def test_articles_outcome_empty_list() -> None:
    o = ArticlesOutcome(rss_url="http://x/feed", articles=[])
    assert o.rss_url == "http://x/feed"
    assert o.articles == []


def test_source_unavailable_roundtrip() -> None:
    u = SourceUnavailableOutcome(rss_url="http://x", reason="boom")
    data = u.model_dump()
    assert data["rss_url"] == "http://x"
    assert data["reason"] == "boom"
    restored = SourceUnavailableOutcome.model_validate(data)
    assert restored == u


def test_source_health_payload_json_body_contract() -> None:
    p = SourceHealthPayload(source_id="s1", status="unavailable", reason="timeout")
    body = json.dumps(p.model_dump())
    loaded = json.loads(body)
    assert loaded == {"type": "source_health", "source_id": "s1", "status": "unavailable", "reason": "timeout"}


def test_articles_outcome_with_normalized_model() -> None:
    a = NormalizedArticleModel(
        article_id="article_id",
        url="http://a",
        title="T",
        body="B",
        summary="S",
        source_id="src",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    o = ArticlesOutcome(rss_url="http://rss", articles=[a])
    assert len(o.articles) == 1
    assert o.articles[0].title == "T"
