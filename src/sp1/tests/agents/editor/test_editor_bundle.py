"""Tests for EditorAgent bundle composition and score aggregation.

Unit tests: no SPADE runtime.  We instantiate EditorAgent with a real Blackboard
and exercise ``_compose_bundle``, ``_aggregate_scores``, and the on-the-fly
scoring fallback directly.
"""

from __future__ import annotations

import hashlib

import pytest

from sp1.agents.editor.editor import EditorAgent
from sp1.agents.models.editor_params import EditorParams
from sp1.infra.blackboard import Blackboard
from sp1.infra.llm_config import LLMConfig


def _make_editor(blackboard: Blackboard) -> EditorAgent:
    return EditorAgent(
        EditorParams(
            jid="editor@localhost",
            password="testpass",
            blackboard=blackboard,
            clerk_jid="clerk@localhost",
            llm_config=LLMConfig(summarization_model="mistral", base_url="http://localhost:11434"),
            relevance_weight=1.0,
            credibility_weight=1.0,
            novelty_weight=1.0,
            min_credibility_threshold=0.3,
            standing_poll_interval_seconds=60,
        )
    )


class TestEditorAggregateScores:
    def test_equal_weights_average(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        scores = {"relevance": 0.8, "credibility": 0.6, "novelty": 0.4}
        agg = editor._aggregate_scores(scores)
        assert agg == pytest.approx(0.6, abs=0.01)

    def test_missing_dimensions_default_zero(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        scores = {"relevance": 1.0}
        agg = editor._aggregate_scores(scores)
        assert agg == pytest.approx(0.333, abs=0.01)

    def test_all_zero(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        assert editor._aggregate_scores({}) == 0.0


class TestEditorConflictResolution:
    def test_high_relevance_low_credibility(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        flag = editor._resolve_conflict({"relevance": 0.8, "credibility": 0.2})
        assert flag == "high_relevance_low_credibility"

    def test_high_credibility_low_relevance(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        flag = editor._resolve_conflict({"relevance": 0.1, "credibility": 0.8})
        assert flag == "high_credibility_low_relevance"

    def test_no_conflict(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        assert editor._resolve_conflict({"relevance": 0.5, "credibility": 0.5}) is None


class TestEditorOnTheFlyScoring:
    @pytest.mark.asyncio
    async def test_on_the_fly_scores_all_articles(self) -> None:
        bb = Blackboard()
        await bb.add_articles(
            [
                {
                    "article_id": "a1",
                    "title": "GPT-5 Released",
                    "body": "GPT-5 is here.",
                },
                {
                    "article_id": "a2",
                    "title": "Climate Summit",
                    "body": "Climate summit news.",
                },
            ]
        )
        editor = _make_editor(bb)
        filter_ = {"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"}
        await bb.register_filter(filter_)

        scores = await editor._score_pool_on_the_fly("f1", filter_, "ui_user")
        # Each article gets 3 dimensions
        assert len(scores) == 6
        # a1 relevance should be high
        a1_rel = [s["score"] for s in scores if s["article_id"] == "a1" and s["dimension"] == "relevance"]
        assert a1_rel[0] > 0.5

    @pytest.mark.asyncio
    async def test_on_the_fly_empty_pool(self) -> None:
        bb = Blackboard()
        editor = _make_editor(bb)
        filter_: dict = {"filter_id": "f1", "keywords": ["AI"], "mode": "one_off"}
        scores = await editor._score_pool_on_the_fly("f1", filter_, "ui_user")
        assert scores == []

    @pytest.mark.asyncio
    async def test_on_the_fly_keyword_in_title(self) -> None:
        bb = Blackboard()
        await bb.add_articles(
            [
                {
                    "article_id": "a1",
                    "title": "GPT-5 Multi-Modal",
                    "body": "OpenAI GPT-5 with multi-modal reasoning.",
                }
            ]
        )
        editor = _make_editor(bb)
        filter_ = {"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"}
        scores = await editor._score_pool_on_the_fly("f1", filter_, "ui_user")
        rel = [s["score"] for s in scores if s["dimension"] == "relevance"]
        assert rel[0] > 0.5


class TestEditorComposeBundle:
    @pytest.mark.asyncio
    async def test_compose_bundle_with_precomputed_scores(self) -> None:
        bb = Blackboard()
        aid = hashlib.md5("demo".encode(), usedforsecurity=False).hexdigest()
        await bb.add_articles(
            [
                {
                    "article_id": aid,
                    "title": "GPT News",
                    "body": "GPT is great.",
                    "source_id": "techcrunch",
                }
            ]
        )
        await bb.register_filter({"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"})
        # Pre-compute scores
        for dim, score in (
            ("relevance", 0.9),
            ("credibility", 0.7),
            ("novelty", 0.6),
        ):
            await bb.write_score_vector(
                {
                    "article_id": aid,
                    "filter_id": "f1",
                    "dimension": dim,
                    "score": score,
                }
            )

        editor = _make_editor(bb)
        bundle = await editor._compose_bundle("f1", "user", "one_off", max_items=5)
        assert bundle is not None
        assert len(bundle["articles"]) >= 1
        art = bundle["articles"][0]
        assert art["article_id"] == aid
        assert art["scores"]["aggregated"] > 0.5

    @pytest.mark.asyncio
    async def test_compose_bundle_on_the_fly_fallback(self) -> None:
        bb = Blackboard()
        await bb.add_articles(
            [
                {
                    "article_id": "a1",
                    "title": "GPT-5 Released",
                    "body": "The new GPT-5 model features multi-modal capabilities.",
                    "source_id": "techcrunch",
                }
            ]
        )
        await bb.register_filter({"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"})
        # No pre-computed scores — should fall back to on-the-fly
        editor = _make_editor(bb)
        bundle = await editor._compose_bundle("f1", "user", "one_off", max_items=5)
        assert bundle is not None
        assert len(bundle["articles"]) >= 1
        assert bundle["articles"][0]["article_id"] == "a1"

    @pytest.mark.asyncio
    async def test_compose_bundle_no_articles(self) -> None:
        bb = Blackboard()
        await bb.register_filter({"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"})
        editor = _make_editor(bb)
        bundle = await editor._compose_bundle("f1", "user", "one_off", max_items=5)
        assert bundle is None

    @pytest.mark.asyncio
    async def test_compose_bundle_diversity_limit_same_source(self) -> None:
        bb = Blackboard()
        for i in range(4):
            await bb.add_articles(
                [
                    {
                        "article_id": f"a{i}",
                        "title": f"Article {i}",
                        "body": f"Body {i} GPT keyword.",
                        "source_id": "techcrunch",
                    }
                ]
            )
        await bb.register_filter({"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"})
        editor = _make_editor(bb)
        bundle = await editor._compose_bundle("f1", "user", "one_off", max_items=10)
        assert bundle is not None
        # Bundle should respect diversity (max 2 per source)
        techcrunch_count = sum(1 for a in bundle["articles"] if a["source_id"] == "techcrunch")
        assert techcrunch_count <= 2

    @pytest.mark.asyncio
    async def test_compose_bundle_skips_severe_conflict(self) -> None:
        bb = Blackboard()
        aid = "a_conflict"
        await bb.add_articles(
            [
                {
                    "article_id": aid,
                    "title": "Clickbait GPT",
                    "body": "GPT! Shocking! You won't believe!",
                    "source_id": "low_cred",
                }
            ]
        )
        await bb.register_filter({"filter_id": "f1", "keywords": ["GPT"], "mode": "one_off"})
        # Inject a conflict score with very low credibility
        await bb.write_score_vector(
            {
                "article_id": aid,
                "filter_id": "f1",
                "dimension": "relevance",
                "score": 0.8,
            }
        )
        await bb.write_score_vector(
            {
                "article_id": aid,
                "filter_id": "f1",
                "dimension": "credibility",
                "score": 0.05,
            }
        )
        editor = _make_editor(bb)
        bundle = await editor._compose_bundle("f1", "user", "one_off", max_items=5)
        # Either no articles or the conflict article is skipped
        if bundle and bundle["articles"]:
            assert all(a["article_id"] != aid for a in bundle["articles"])
