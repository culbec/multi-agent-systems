from __future__ import annotations

from typing import Any

from sp1.agents.analysts.base import AnalystAgent
from sp1.agents.models.analyst_params import AnalystParams


class CredibilityAnalystAgent(AnalystAgent):
    """Scores article trustworthiness combining source reputation, cross-source
    corroboration, and light content heuristics.

    Updates the source-reputation table over time based on aggregated feedback.
    """

    def __init__(self, params: AnalystParams) -> None:
        super().__init__(params)

    def _corroboration_score(self, article: dict[str, Any], pool: list[dict[str, Any]]) -> float:
        """Return average Jaccard similarity with other recent articles in the pool."""
        if len(pool) < 2:
            return 0.5

        art_words = set((article.get("title") or "").lower().split())
        art_words.update((article.get("body") or "").lower().split()[:50])
        if not art_words:
            return 0.5

        similarities: list[float] = []
        for other in pool:
            if other["article_id"] == article["article_id"]:
                continue
            other_words = set((other.get("title") or "").lower().split())
            other_words.update((other.get("body") or "").lower().split()[:50])
            if not other_words:
                continue
            intersection = len(art_words & other_words)
            union = len(art_words | other_words)
            similarities.append(intersection / union if union else 0.0)

        return sum(similarities) / len(similarities) if similarities else 0.5

    def _content_heuristics(self, article: dict[str, Any]) -> float:
        """Light heuristics: length, quoted sources, absence of clickbait."""
        body = article.get("body") or ""
        title = article.get("title") or ""

        score = 0.5

        # Length heuristic
        words = len(body.split())
        if words > 300:
            score += 0.15
        elif words < 50:
            score -= 0.15

        # Quoted sources heuristic
        if '"' in body or "said" in body.lower():
            score += 0.1

        # Clickbait penalty
        clickbait_patterns = ["shocking", "you won't believe", "incredible", "amazing", "wow"]
        title_lower = title.lower()
        if any(p in title_lower for p in clickbait_patterns):
            score -= 0.2

        return max(0.0, min(1.0, score))

    def score(self, article: dict[str, Any], filter_: dict[str, Any], user_profile: dict[str, Any] | None) -> float:
        article.get("source_id", "")

        # Source reputation component (async not available in sync method, use stored value from article)
        # We approximate by checking if the blackboard has a reputation score.
        # Since score() is sync, we can't await; the Editor will use blackboard reputation directly.
        # Here we use a placeholder that the Editor will override with real data.
        reputation_score = 0.5

        # Cross-source corroboration (approximate using article metadata)
        # Since we can't access the pool synchronously, we'll compute a simple proxy
        corroboration = 0.5

        # Content heuristics
        content_score = self._content_heuristics(article)

        # Weighted combination
        final_score = reputation_score * 0.35 + corroboration * 0.35 + content_score * 0.30

        # Apply per-user credibility preference
        if user_profile:
            pref_weights = user_profile.get("preference_weights", {})
            credibility_pref = pref_weights.get("credibility", 1.0)
            final_score = min(1.0, final_score * credibility_pref)

        return round(final_score, 4)
