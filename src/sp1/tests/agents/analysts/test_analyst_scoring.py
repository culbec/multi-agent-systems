"""Tests for the three analyst agents.

These are pure unit tests: they instantiate the analyst agents directly and
invoke ``.score()`` with synthetic article/filter/user_profile dicts.  No
SPADE runtime is needed.
"""

from __future__ import annotations

import pytest

from sp1.agents.analysts.credibility_analyst import CredibilityAnalystAgent
from sp1.agents.analysts.novelty_analyst import NoveltyAnalystAgent
from sp1.agents.analysts.relevance_analyst import RelevanceAnalystAgent
from sp1.agents.models.analyst_params import AnalystParams
from sp1.infra.blackboard import Blackboard


def _make_params(dimension: str) -> AnalystParams:
    return AnalystParams(
        jid=f"analyst_{dimension}@localhost",
        password="testpass",
        blackboard=Blackboard(),
        editor_jid="editor@localhost",
        dimension=dimension,
        poll_interval_seconds=30,
    )


# ---------------------------------------------------------------------------
# RelevanceAnalystAgent
# ---------------------------------------------------------------------------


class TestRelevanceAnalyst:
    @pytest.fixture
    def agent(self) -> RelevanceAnalystAgent:
        return RelevanceAnalystAgent(_make_params("relevance"))

    def test_exact_keyword_match(self, agent: RelevanceAnalystAgent) -> None:
        article = {"title": "OpenAI GPT-5 Released", "body": "The new GPT-5 model is amazing."}
        filter_ = {"keywords": ["GPT"], "categories": []}
        score = agent.score(article, filter_, None)
        assert score > 0.5

    def test_hyphenated_keyword_match(self, agent: RelevanceAnalystAgent) -> None:
        """'GPT' should match 'GPT-5' in text."""
        article = {"title": "OpenAI GPT-5 Released", "body": "The new GPT-5 model is amazing."}
        filter_ = {"keywords": ["GPT"], "categories": []}
        score = agent.score(article, filter_, None)
        assert score > 0.0

    def test_multi_word_keyword_match(self, agent: RelevanceAnalystAgent) -> None:
        article = {"title": "Climate Change Summit", "body": "The climate change summit was productive."}
        filter_ = {"keywords": ["climate change"], "categories": []}
        score = agent.score(article, filter_, None)
        assert score > 0.5

    def test_no_keywords_neutral(self, agent: RelevanceAnalystAgent) -> None:
        article = {"title": "Something", "body": "Body text here."}
        filter_ = {"keywords": [], "categories": []}
        score = agent.score(article, filter_, None)
        assert score == pytest.approx(0.5)

    def test_no_match_returns_zero_or_low(self, agent: RelevanceAnalystAgent) -> None:
        article = {"title": "Basketball Finals", "body": "The finals were intense."}
        filter_ = {"keywords": ["quantum"], "categories": []}
        score = agent.score(article, filter_, None)
        assert score < 0.3

    def test_category_bonus(self, agent: RelevanceAnalystAgent) -> None:
        article = {
            "title": "Tech News",
            "body": "Some tech news.",
            "categories": ["technology", "AI"],
        }
        filter_ = {"keywords": ["news"], "categories": ["technology"]}
        score = agent.score(article, filter_, None)
        assert score > 0.5

    def test_user_profile_preference_boost(self, agent: RelevanceAnalystAgent) -> None:
        article = {"title": "Quantum Computing", "body": "Quantum news."}
        filter_ = {"keywords": ["quantum"], "categories": []}
        user_profile = {"preference_weights": {"relevance": 1.5}}
        score_with_pref = agent.score(article, filter_, user_profile)
        score_without = agent.score(article, filter_, None)
        assert score_with_pref >= score_without


# ---------------------------------------------------------------------------
# CredibilityAnalystAgent
# ---------------------------------------------------------------------------


class TestCredibilityAnalyst:
    @pytest.fixture
    def agent(self) -> CredibilityAnalystAgent:
        return CredibilityAnalystAgent(_make_params("credibility"))

    def test_long_article_scores_higher(self, agent: CredibilityAnalystAgent) -> None:
        long_body = "word " * 400
        short_body = "short."
        article_long = {"title": "Title", "body": long_body}
        article_short = {"title": "Title", "body": short_body}
        score_long = agent.score(article_long, {}, None)
        score_short = agent.score(article_short, {}, None)
        assert score_long > score_short

    def test_clickbait_penalty(self, agent: CredibilityAnalystAgent) -> None:
        article = {"title": "Shocking! You won't believe this!", "body": "word " * 300}
        score = agent.score(article, {}, None)
        clean = {"title": "Senate Passes Bill", "body": "word " * 300}
        score_clean = agent.score(clean, {}, None)
        assert score < score_clean

    def test_quoted_sources_bonus(self, agent: CredibilityAnalystAgent) -> None:
        article = {"title": "Title", "body": 'The CEO said, "We are expanding." word ' * 100}
        score = agent.score(article, {}, None)
        no_quotes = {"title": "Title", "body": "word " * 300}
        score_no_quotes = agent.score(no_quotes, {}, None)
        assert score >= score_no_quotes

    def test_user_profile_preference_boost(self, agent: CredibilityAnalystAgent) -> None:
        article = {"title": "Title", "body": "word " * 300}
        user_profile = {"preference_weights": {"credibility": 2.0}}
        score_boosted = agent.score(article, {}, user_profile)
        score_normal = agent.score(article, {}, None)
        assert score_boosted >= score_normal


# ---------------------------------------------------------------------------
# NoveltyAnalystAgent
# ---------------------------------------------------------------------------


class TestNoveltyAnalyst:
    @pytest.fixture
    def agent(self) -> NoveltyAnalystAgent:
        return NoveltyAnalystAgent(_make_params("novelty"))

    def test_longer_body_scores_higher(self, agent: NoveltyAnalystAgent) -> None:
        long = {"title": "Title", "body": "word " * 600, "categories": []}
        short = {"title": "Title", "body": "short.", "categories": []}
        assert agent.score(long, {}, None) > agent.score(short, {}, None)

    def test_unique_title_scores_higher(self, agent: NoveltyAnalystAgent) -> None:
        unique = {"title": "Quantum Supremacy Achieved in Silicon Valley Lab", "body": "word " * 100, "categories": []}
        generic = {"title": "The News Report", "body": "word " * 100, "categories": []}
        assert agent.score(unique, {}, None) > agent.score(generic, {}, None)

    def test_more_categories_score_higher(self, agent: NoveltyAnalystAgent) -> None:
        many = {"title": "Title", "body": "word " * 100, "categories": ["a", "b", "c", "d"]}
        few = {"title": "Title", "body": "word " * 100, "categories": ["a"]}
        assert agent.score(many, {}, None) > agent.score(few, {}, None)

    def test_user_profile_preference_boost(self, agent: NoveltyAnalystAgent) -> None:
        article = {"title": "Title", "body": "word " * 300, "categories": ["tech"]}
        user_profile = {"preference_weights": {"novelty": 1.5}}
        score_boosted = agent.score(article, {}, user_profile)
        score_normal = agent.score(article, {}, None)
        assert score_boosted >= score_normal
