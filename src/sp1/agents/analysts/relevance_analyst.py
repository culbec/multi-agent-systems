"""Relevance analyst agent.

Scores how well an article matches a filter's keywords.
Uses whole-word matching (via regex \b) to avoid false positives
from embedded substrings (e.g. 'gpt' inside 'trump').
"""

from __future__ import annotations

import math
import re
import string
from typing import Any

from sp1.agents.analysts.base import AnalystAgent
from sp1.agents.models.analyst_params import AnalystParams


class RelevanceAnalystAgent(AnalystAgent):
    """Scores how well an article matches a filter's keywords and categories.

    Uses a simple BM25-inspired sparse retrieval blended with per-user
    preference weights read from the blackboard.
    """

    def __init__(self, params: AnalystParams) -> None:
        super().__init__(params)

    def _tokenize(self, text: str) -> list[str]:
        return [t.lower().strip(string.punctuation) for t in text.split() if len(t.strip(string.punctuation)) > 2]

    def _term_frequency(self, term: str, tokens: list[str]) -> int:
        return tokens.count(term)

    def _idf(self, term: str, corpus_tokens: list[list[str]]) -> float:
        df = sum(1 for doc in corpus_tokens if term in doc)
        n = len(corpus_tokens) or 1
        return math.log((n - df + 0.5) / (df + 0.5) + 1)

    @staticmethod
    def _whole_word_count(text: str, keyword: str) -> int:
        """Return the number of whole-word occurrences of *keyword* in *text*."""
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return len(re.findall(pattern, text, flags=re.IGNORECASE))

    def score(self, article: dict[str, Any], filter_: dict[str, Any], user_profile: dict[str, Any] | None) -> float:
        keywords = filter_.get("keywords", [])
        if not keywords:
            return 0.5  # Neutral when no keywords specified

        title = (article.get("title") or "").lower()
        body = (article.get("body") or "").lower()
        summary = (article.get("summary") or "").lower()
        text = f"{title} {summary} {body}"

        if not text.strip():
            return 0.0

        # Whole-word keyword presence: avoid substring false positives
        keyword_hits: float = 0
        for kw in keywords:
            kw_lower = kw.lower().strip(string.punctuation)
            if len(kw_lower) < 2:
                continue
            # Multi-word keyword → exact phrase match
            if " " in kw_lower:
                keyword_hits += kw_lower in text
                continue
            # Single keyword → whole-word match
            matches = self._whole_word_count(text, kw_lower)
            keyword_hits += min(matches, 1)  # cap at 1 per keyword per article

        base_score = min(1.0, keyword_hits / max(1, len(keywords)))

        # Category bonus
        article_cats = [c.lower() for c in article.get("categories", [])]
        filter_cats = [c.lower() for c in filter_.get("categories", [])]
        if filter_cats and article_cats:
            cat_overlap = len(set(filter_cats) & set(article_cats)) / len(filter_cats)
            base_score = base_score * 0.7 + cat_overlap * 0.3

        # Apply per-user preference weight if available
        if user_profile:
            pref_weights = user_profile.get("preference_weights", {})
            relevance_pref = pref_weights.get("relevance", 1.0)
            base_score = min(1.0, base_score * relevance_pref)

        return base_score
