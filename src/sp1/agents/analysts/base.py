from __future__ import annotations

import asyncio
from abc import abstractmethod

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour

from sp1.utils.logger import get_logger


class AnalystAgent(Agent):
    """Abstract base for all Analyst agents.

    Each analyst continuously monitors the candidate pool and active filters,
    computes a dimension-specific score, and writes score vectors to the
    blackboard.  Analysts do **not** communicate with one another; their
    independence is an architectural commitment.
    """

    def __init__(self, params: AnalystParams) -> None:  # noqa: F821
        super().__init__(params.jid, params.password)
        self.log = get_logger(str(self.jid))
        self._blackboard = params.blackboard
        self._editor_jid = params.editor_jid
        self._dimension = params.dimension
        self._poll_interval_seconds = params.poll_interval_seconds
        self._last_seen_article_count: int = 0

    @abstractmethod
    def score(self, article: dict, filter_: dict, user_profile: dict | None) -> float:
        """Return a score in ``[0, 1]`` for the given article/filter pair."""

    async def _score_all_pending(self) -> None:
        articles = await self._blackboard.snapshot_candidate_pool()
        filters = await self._blackboard.get_all_filters()

        if not articles or not filters:
            return

        # Only score newly arrived articles (simple optimisation)
        new_articles = articles[self._last_seen_article_count :]
        if not new_articles:
            return

        self._last_seen_article_count = len(articles)

        for article in new_articles:
            for f in filters:
                user_id = f.get("user_id", "default_user")
                user_profile = await self._blackboard.get_user_profile(user_id)

                score = self.score(article, f, user_profile)
                if score is None:
                    continue

                vector = {
                    "article_id": article["article_id"],
                    "filter_id": f["filter_id"],
                    "user_id": user_id,
                    "dimension": self._dimension,
                    "score": round(score, 4),
                    "scored_at": "",
                }
                await self._blackboard.write_score_vector(vector)
                self.log.debug(
                    "Scored %s for article=%s filter=%s score=%.4f",
                    self._dimension,
                    article["article_id"],
                    f["filter_id"],
                    score,
                )

    class ScoreCycle(CyclicBehaviour):
        async def run(self) -> None:
            await self.agent._score_all_pending()
            await asyncio.sleep(self.agent._poll_interval_seconds)

    async def setup(self) -> None:
        self.log.info("%s starting (dimension=%s)...", self.jid, self._dimension)
        self.add_behaviour(self.ScoreCycle())
