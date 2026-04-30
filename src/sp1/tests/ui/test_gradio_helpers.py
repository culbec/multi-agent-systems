"""Tests for Gradio UI helper functions.

Unit tests for sorting, formatting, and filtering logic.  No Gradio server is
started.
"""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("SPADE_SERVER", "localhost")

from sp1.ui.gradio_app import (
    SP1_LATEST_THRESHOLD,
    _format_bundle_simple,
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


class TestGetLatestArticlesSortLogic:
    def test_sorts_by_date_descending(self) -> None:
        articles = [
            _article("a1", "2026-05-01T10:00:00+00:00"),
            _article("a2", "2026-05-01T12:00:00+00:00"),
            _article("a3", "2026-05-01T08:00:00+00:00"),
        ]

        def _published_at(a: dict) -> str:
            return a.get("published_at") or "1970-01-01T00:00:00+00:00"

        sorted_articles = sorted(articles, key=_published_at, reverse=True)
        assert sorted_articles[0]["article_id"] == "a2"
        assert sorted_articles[1]["article_id"] == "a1"
        assert sorted_articles[2]["article_id"] == "a3"

    def test_limits_to_threshold(self) -> None:
        articles = [_article(f"a{i}", f"2026-05-01T{i:02d}:00:00+00:00") for i in range(15)]
        limited = sorted(articles, key=lambda a: a["published_at"], reverse=True)[:SP1_LATEST_THRESHOLD]
        assert len(limited) <= SP1_LATEST_THRESHOLD


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
