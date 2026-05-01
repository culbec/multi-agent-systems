"""Tests for blackboard filter matching and standing-filter registry."""

from __future__ import annotations

import pytest
import pytest_asyncio

from sp1.infra.blackboard import Blackboard


class TestBlackboardFilterMatching:
    @pytest_asyncio.fixture
    async def bb_with_articles(self) -> Blackboard:
        bb = Blackboard()
        await bb.add_articles(
            [
                {
                    "article_id": "a1",
                    "title": "GPT-5 Released by OpenAI",
                    "body": "OpenAI announced GPT-5 with multi-modal capabilities.",
                    "summary": "OpenAI GPT-5",
                    "categories": ["technology", "AI"],
                    "published_at": "2026-05-01T10:00:00+00:00",
                    "source_id": "techcrunch",
                },
                {
                    "article_id": "a2",
                    "title": "Climate Summit Reaches Agreement",
                    "body": "The climate summit in Geneva reached a landmark agreement.",
                    "summary": "Climate agreement",
                    "categories": ["politics", "environment"],
                    "published_at": "2026-05-01T08:00:00+00:00",
                    "source_id": "reuters",
                },
                {
                    "article_id": "a3",
                    "title": "Quantum Computing Breakthrough",
                    "body": "A new quantum algorithm.",
                    "summary": "Quantum news",
                    "categories": ["technology", "science"],
                    "published_at": "2026-05-01T12:00:00+00:00",
                    "source_id": "nytimes",
                },
            ]
        )
        return bb

    @pytest.mark.asyncio
    async def test_keyword_filter_any(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": ["GPT", "climate"],
                "keyword_mode": "any",
                "categories": [],
                "sources": [],
            }
        )
        ids = {r["article_id"] for r in results}
        assert "a1" in ids  # GPT
        assert "a2" in ids  # climate

    @pytest.mark.asyncio
    async def test_keyword_filter_all(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": ["OpenAI", "GPT"],
                "keyword_mode": "all",
                "categories": [],
                "sources": [],
            }
        )
        ids = {r["article_id"] for r in results}
        assert "a1" in ids
        assert "a2" not in ids

    @pytest.mark.asyncio
    async def test_category_filter(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": [],
                "keyword_mode": "any",
                "categories": ["technology"],
                "sources": [],
            }
        )
        ids = {r["article_id"] for r in results}
        assert "a1" in ids  # technology
        assert "a3" in ids  # technology
        assert "a2" not in ids  # politics, environment

    @pytest.mark.asyncio
    async def test_source_filter(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": [],
                "keyword_mode": "any",
                "categories": [],
                "sources": ["reuters"],
            }
        )
        ids = {r["article_id"] for r in results}
        assert ids == {"a2"}

    @pytest.mark.asyncio
    async def test_combined_filter(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": ["GPT"],
                "keyword_mode": "any",
                "categories": ["technology"],
                "sources": ["techcrunch"],
            }
        )
        ids = {r["article_id"] for r in results}
        assert ids == {"a1"}

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, bb_with_articles: Blackboard) -> None:
        results = await bb_with_articles.get_articles_for_filter(
            {
                "keywords": ["zoology"],
                "keyword_mode": "any",
                "categories": [],
                "sources": [],
            }
        )
        assert results == []


class TestBlackboardStandingFilters:
    @pytest.mark.asyncio
    async def test_standing_filter_registry(self) -> None:
        bb = Blackboard()
        await bb.register_filter(
            {
                "filter_id": "f1",
                "keywords": ["AI"],
                "mode": "standing",
                "user_id": "u1",
                "delivery": {"max_items": 5},
            }
        )
        standing = await bb.get_standing_filters()
        assert len(standing) == 1
        assert standing[0]["filter_id"] == "f1"

    @pytest.mark.asyncio
    async def test_standing_filter_excludes_one_off(self) -> None:
        bb = Blackboard()
        await bb.register_filter(
            {
                "filter_id": "f1",
                "keywords": ["AI"],
                "mode": "one_off",
                "user_id": "u1",
            }
        )
        standing = await bb.get_standing_filters()
        assert len(standing) == 0


class TestBlackboardDeliveryQueue:
    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self) -> None:
        bb = Blackboard()
        await bb.enqueue_delivery("user1", {"article_id": "a1", "bundle_id": "b1"})
        items = await bb.dequeue_deliveries("user1")
        assert len(items) == 1
        assert items[0]["article_id"] == "a1"

    @pytest.mark.asyncio
    async def test_delivery_history(self) -> None:
        bb = Blackboard()
        await bb.record_delivery("user1", "a1", "b1")
        history = await bb.get_delivery_history("user1")
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_feedback_history(self) -> None:
        bb = Blackboard()
        await bb.record_feedback(
            {
                "user_id": "user1",
                "article_id": "a1",
                "filter_id": "f1",
                "relevant": True,
            }
        )
        history = await bb.get_feedback_history("user1")
        assert len(history) == 1
        assert history[0]["relevant"] is True
