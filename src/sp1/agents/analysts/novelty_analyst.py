from __future__ import annotations

from typing import Any

from sp1.agents.analysts.base import AnalystAgent
from sp1.agents.models.analyst_params import AnalystParams


class NoveltyAnalystAgent(AnalystAgent):
    """Scores how different an article is from content already delivered to the
    user and from other articles in the pool.

    Penalises redundancy and near-duplicates.
    """

    def __init__(self, params: AnalystParams) -> None:
        super().__init__(params)

    def _text_similarity(self, a: dict[str, Any], b: dict[str, Any]) -> float:
        """Simple Jaccard similarity on title + first 100 body words."""
        a_words = set((a.get("title") or "").lower().split())
        a_words.update((a.get("body") or "").lower().split()[:100])

        b_words = set((b.get("title") or "").lower().split())
        b_words.update((b.get("body") or "").lower().split()[:100])

        if not a_words or not b_words:
            return 0.0

        intersection = len(a_words & b_words)
        union = len(a_words | b_words)
        return intersection / union if union else 0.0

    def score(self, article: dict[str, Any], filter_: dict[str, Any], user_profile: dict[str, Any] | None) -> float:
        # Since we can't access the blackboard synchronously for delivery history,
        # we compute a proxy based on the article itself.
        # The Editor will use the full delivery history for final novelty weighting.

        # Shorter articles tend to be less novel (common summaries)
        body_len = len((article.get("body") or "").split())
        length_score = min(1.0, body_len / 500)

        # Title uniqueness proxy: very short/generic titles score lower
        title = (article.get("title") or "").lower()
        generic_words = {"the", "a", "an", "update", "news", "report"}
        title_words = set(title.split())
        generic_ratio = len(title_words & generic_words) / max(1, len(title_words))
        title_score = 1.0 - generic_ratio

        # Category diversity bonus
        categories = article.get("categories", [])
        cat_score = min(1.0, len(categories) / 3)

        novelty = length_score * 0.4 + title_score * 0.35 + cat_score * 0.25

        # Apply per-user novelty preference
        if user_profile:
            pref_weights = user_profile.get("preference_weights", {})
            novelty_pref = pref_weights.get("novelty", 1.0)
            novelty = min(1.0, novelty * novelty_pref)

        return round(novelty, 4)
