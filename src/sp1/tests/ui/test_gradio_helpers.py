"""Tests for Gradio UI helper functions.

Unit tests for sorting, formatting, and filtering logic.  No Gradio server is
started.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import MagicMock

os.environ.setdefault("SPADE_SERVER", "localhost")

from sp1.ui.gradio_app import (
    SP1_LATEST_THRESHOLD,
    _format_bundle_simple,
    get_bundle_detail,
    get_bundles,
    get_delivery_history,
    get_feedback_history,
    get_latest_articles,
    get_message_log,
    get_pending_deliveries,
    get_source_reputation,
    get_user_profiles,
    manager,
)


def _article(article_id: str, published_at: str, **kwargs: Any) -> dict:
    base = {
        "article_id": article_id,
        "title": f"Article {article_id}",
        "body": "Body text.",
        "source_id": "test",
        "summary": "Summary.",
        "url": f"http://example.com/{article_id}",
        "published_at": published_at,
    }
    base.update(kwargs)
    return base


class _MockBlackboard:
    def __init__(self, articles: list[dict]) -> None:
        self._articles = articles

    async def snapshot_candidate_pool(self) -> list[dict]:
        return list(self._articles)


def _sync_run(coro: Any, timeout: float = 10.0) -> Any:
    return asyncio.run(coro)


class TestGetLatestArticlesSortLogic:
    def test_sorts_by_date_descending(self) -> None:
        articles = [
            _article("a1", "2026-05-01T10:00:00+00:00"),
            _article("a2", "2026-05-01T12:00:00+00:00"),
            _article("a3", "2026-05-01T08:00:00+00:00"),
        ]
        mock_bb = _MockBlackboard(articles)
        original_bb = manager._blackboard
        original_run = manager.run
        manager._blackboard = mock_bb
        manager.run = _sync_run
        try:
            result = get_latest_articles()
        finally:
            manager._blackboard = original_bb
            manager.run = original_run

        assert len(result) == 3
        assert result[0]["article_id"] == "a2"
        assert result[1]["article_id"] == "a1"
        assert result[2]["article_id"] == "a3"

    def test_limits_to_threshold(self) -> None:
        articles = [_article(f"a{i}", f"2026-05-01T{i:02d}:00:00+00:00") for i in range(15)]
        mock_bb = _MockBlackboard(articles)
        original_bb = manager._blackboard
        original_run = manager.run
        manager._blackboard = mock_bb
        manager.run = _sync_run
        try:
            result = get_latest_articles()
        finally:
            manager._blackboard = original_bb
            manager.run = original_run

        assert len(result) == min(len(articles), SP1_LATEST_THRESHOLD)

    def test_empty_pool(self) -> None:
        mock_bb = _MockBlackboard([])
        original_bb = manager._blackboard
        original_run = manager.run
        manager._blackboard = mock_bb
        manager.run = _sync_run
        try:
            result = get_latest_articles()
        finally:
            manager._blackboard = original_bb
            manager.run = original_run

        assert result == []


class TestGetBundles:
    def test_empty_bundles(self) -> None:
        result = get_bundles()
        assert "No bundles" in result

    def test_bundle_detail_not_found(self) -> None:
        result = get_bundle_detail("nonexistent")
        assert "not found" in result


class TestMessageLog:
    def test_empty_log(self) -> None:
        result = get_message_log()
        assert "No messages" in result


class TestDebugHelpers:
    def test_source_reputation_empty(self) -> None:
        result = get_source_reputation()
        assert "No source reputation" in result

    def test_user_profiles_empty(self) -> None:
        result = get_user_profiles()
        assert "No user profiles" in result

    def test_pending_deliveries_empty(self) -> None:
        result = get_pending_deliveries()
        assert "No pending" in result

    def test_delivery_history_empty(self) -> None:
        result = get_delivery_history()
        assert "No delivery" in result

    def test_feedback_history_empty(self) -> None:
        result = get_feedback_history()
        assert "No feedback" in result


class TestFormatBundleSimple:
    def test_empty_articles(self) -> None:
        result = _format_bundle_simple([], preamble="Results")
        assert "Results" in result

    def test_includes_preamble(self) -> None:
        articles = [
            {
                "title": "Test Article",
                "source_id": "src",
                "scores": {
                    "relevance": 0.8,
                    "credibility": 0.7,
                    "novelty": 0.6,
                },
                "summary": "A test article.",
                "url": "http://example.com/1",
            }
        ]
        result = _format_bundle_simple(articles, preamble="Custom preamble")
        assert "Custom preamble" in result
        assert "Test Article" in result
        assert "0.8" in result
        assert "💡 Tips" in result

    def test_includes_tips(self) -> None:
        articles = [
            {
                "title": "T",
                "source_id": "s",
                "scores": {},
                "summary": "summary",
                "url": "#",
            }
        ]
        result = _format_bundle_simple(articles)
        assert "💡 Tips" in result
        assert "/filter" in result
        assert "/standing" in result
