from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import aiohttp
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from sp1.agents.models.editor_params import EditorParams
from sp1.infra.config import SP1Config
from sp1.infra.messages import (
    BundleDeliveryMessage,
    BundleFailureMessage,
    BundleRequestMessage,
    FilterRegisteredMessage,
    FilterRemovedMessage,
    SourceHealthMessage,
)
from sp1.infra.ontology import ONTOLOGY_EDITOR
from sp1.utils.logger import get_logger


class EditorAgent(Agent):
    """Central decision-making agent.

    * For one-off filter requests: aggregates score vectors, composes a diverse
      bundle respecting delivery preferences, generates per-article summaries,
      and returns the bundle to the Clerk.
    * For standing filters: continuously watches the score board and autonomously
      decides when readiness criteria are met, then composes and pushes a bundle.
    """

    def __init__(self, params: EditorParams) -> None:
        super().__init__(params.jid, params.password)
        self.log = get_logger(str(self.jid))
        self._config = SP1Config()
        self._blackboard = params.blackboard
        self._clerk_jid = params.clerk_jid
        self._relevance_weight = params.relevance_weight
        self._credibility_weight = params.credibility_weight
        self._novelty_weight = params.novelty_weight
        self._min_credibility_threshold = params.min_credibility_threshold
        self._llm_config = params.llm_config

        # Standing filter state: filter_id -> readiness counter
        self._standing_state: dict[str, dict[str, Any]] = {}

    ##############################
    # Summarisation
    ##############################

    async def _summarise_article(self, article: dict[str, Any]) -> str:
        """Generate a short summary for *article* using the configured Ollama model.

        Falls back to the article's existing ``summary`` field when the LLM is
        unreachable and ``fallback_to_extract`` is enabled.
        """
        body = article.get("body", "")
        existing_summary = article.get("summary", "")

        if not body or len(body) < 50:
            return existing_summary or body[:200]

        prompt = f"Summarise the following news article in 2-3 sentences. Be concise and objective:\n\n{body[:2000]}"

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._llm_config.timeout_seconds)
            ) as session:
                payload = {
                    "model": self._llm_config.summarization_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self._llm_config.temperature,
                        "num_predict": self._llm_config.max_tokens,
                    },
                }
                async with session.post(f"{self._llm_config.base_url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        summary = data.get("response", "").strip()
                        if summary:
                            return summary
        except Exception as exc:
            self.log.warning("LLM summarisation failed for %s: %s", article.get("article_id"), exc)

        if self._llm_config.fallback_to_extract:
            return existing_summary or body[:300]

        return "[Summary unavailable]"

    ##############################
    # Score aggregation
    ##############################

    def _aggregate_scores(self, scores: dict[str, float]) -> float:
        """Weighted aggregation of the three analyst dimensions.

        :param scores: Mapping ``{"relevance": float, "credibility": float, "novelty": float}``.
        :return: Aggregated score in ``[0, 1]``.
        """
        relevance = scores.get("relevance", 0.0)
        credibility = scores.get("credibility", 0.0)
        novelty = scores.get("novelty", 0.0)

        weight_sum = self._relevance_weight + self._credibility_weight + self._novelty_weight
        if weight_sum == 0.0:
            return 0.0

        total = (
            self._relevance_weight * relevance
            + self._credibility_weight * credibility
            + self._novelty_weight * novelty
        ) / weight_sum

        return round(total, 4)

    def _resolve_conflict(self, scores: dict[str, float]) -> str | None:
        """Return a conflict flag if dimensions are in tension, else ``None``."""
        relevance = scores.get("relevance", 0.0)
        credibility = scores.get("credibility", 0.0)

        if relevance > 0.7 and credibility < self._min_credibility_threshold:
            return "high_relevance_low_credibility"
        if credibility > 0.7 and relevance < 0.2:
            return "high_credibility_low_relevance"
        return None

    async def _compose_bundle(
        self,
        filter_id: str,
        user_id: str,
        trigger: str,
        max_items: int | None = None,
    ) -> dict[str, Any] | None:
        """Read score board, aggregate, filter, summarise, and compose a bundle.

        If no pre-computed scores exist for this filter (e.g.  the filter was
        just registered), scoring is performed *on-the-fly* by invoking each
        article through the analyst scoring logic directly.  This guarantees
        that a one-off ``/filter`` query always returns results when matching
        articles exist in the candidate pool.
        """
        if max_items is None:
            max_items = self._config.limit_bundle_max_items
        filter_ = await self._blackboard.get_filter(filter_id)
        if filter_ is None:
            return None

        all_scores = await self._blackboard.get_scores_for_filter(filter_id)

        # Fallback: score articles on-the-fly if no pre-computed vectors exist
        if not all_scores:
            self.log.info("No pre-computed scores for %s — computing on-the-fly", filter_id)
            all_scores = await self._score_pool_on_the_fly(filter_id, filter_, user_id)
            if not all_scores:
                return None

        # Group scores by article
        article_scores: dict[str, dict[str, float]] = {}
        for s in all_scores:
            aid = s["article_id"]
            dim = s["dimension"]
            article_scores.setdefault(aid, {})[dim] = s["score"]

        # Also fetch source-reputation overrides for credibility
        pool = await self._blackboard.snapshot_candidate_pool()
        article_map = {a["article_id"]: a for a in pool}

        # Compute aggregated scores
        ranked: list[tuple[str, float, dict[str, float], str | None]] = []
        for aid, scores in article_scores.items():
            # Override credibility with source reputation if available
            article = article_map.get(aid)
            if article:
                source_id = article.get("source_id")
                if source_id:
                    rep = await self._blackboard.get_source_reputation(source_id)
                    if rep is not None:
                        scores["credibility"] = rep

            aggregated = self._aggregate_scores(scores)
            conflict = self._resolve_conflict(scores)
            ranked.append((aid, aggregated, scores, conflict))

        # Sort by aggregated score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        # Select candidate articles (filtering + diversity) BEFORE summarising
        articles_to_summarise: list[tuple[str, dict[str, Any], float, dict[str, float], str | None]] = []
        for aid, agg_score, scores, conflict in ranked:
            if len(articles_to_summarise) >= max_items:
                break

            article = article_map.get(aid)
            if not article:
                continue

            # Skip if credibility is extremely low and relevance is not compensating
            if conflict == "high_relevance_low_credibility" and agg_score < 0.3:
                continue

            # Simple diversity: don't include more than 2 articles from the same source
            source_id = article.get("source_id", "")
            source_count = sum(1 for s in articles_to_summarise if s[1].get("source_id") == source_id)
            if source_count >= 2:
                continue

            articles_to_summarise.append((aid, article, agg_score, scores, conflict))

        # Summarise all candidate articles in parallel (with per-article timeout)
        async def _summarise_with_timeout(art: dict[str, Any]) -> str:
            try:
                return await asyncio.wait_for(
                    self._summarise_article(art),
                    timeout=max(1.0, self._config.timeout_bundle_request / max(len(articles_to_summarise), 1)),
                )
            except asyncio.TimeoutError:
                self.log.warning("Summarisation timed out for %s", art.get("article_id"))
                return art.get("summary") or art.get("body", "")[:300]

        summary_tasks = [_summarise_with_timeout(art) for _, art, _, _, _ in articles_to_summarise]
        summaries = await asyncio.gather(*summary_tasks)

        # Assemble selected articles with their summaries
        selected: list[dict[str, Any]] = []
        for idx, (aid, article, agg_score, scores, conflict) in enumerate(articles_to_summarise):
            source_id = article.get("source_id", "")
            selected.append(
                {
                    "article_id": aid,
                    "source_id": source_id,
                    "title": article.get("title", ""),
                    "url": article.get("url", ""),
                    "summary": summaries[idx],
                    "scores": {
                        "aggregated": agg_score,
                        "relevance": round(scores.get("relevance", 0.0), 4),
                        "credibility": round(scores.get("credibility", 0.0), 4),
                        "novelty": round(scores.get("novelty", 0.0), 4),
                    },
                    "conflict_flag": conflict,
                    "published_at": article.get("published_at", ""),
                }
            )

        if not selected:
            return None

        bundle_id = hashlib.md5(
            f"{filter_id}_{user_id}_{datetime.now(timezone.utc).isoformat()}".encode(),
            usedforsecurity=False,
        ).hexdigest()

        return {
            "bundle_id": bundle_id,
            "filter_id": filter_id,
            "user_id": user_id,
            "trigger": trigger,
            "composed_at": datetime.now(timezone.utc).isoformat(),
            "articles": selected,
        }

    # ------------------------------------------------------------------
    # On-the-fly scoring fallback
    # ------------------------------------------------------------------

    async def _score_pool_on_the_fly(
        self, filter_id: str, filter_: dict[str, Any], user_id: str
    ) -> list[dict[str, Any]]:
        """Score every article in the candidate pool against *filter_*."""
        pool = await self._blackboard.snapshot_candidate_pool()
        if not pool:
            return []

        import re

        def _whole_word_count(text: str, keyword: str) -> int:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            return len(re.findall(pattern, text, flags=re.IGNORECASE))

        def _relevance_score(article: dict[str, Any]) -> float:
            keywords = [k.lower() for k in filter_.get("keywords", [])]
            if not keywords:
                return 0.5
            text = (f"{article.get('title', '')} {article.get('body', '')} {article.get('summary', '')}").lower()
            hits = 0
            for kw in keywords:
                kw = kw.strip()
                if len(kw) < 2:
                    continue
                if " " in kw:
                    hits += kw in text
                else:
                    hits += min(_whole_word_count(text, kw), 1)
            return min(1.0, hits / len(keywords))

        def _credibility_score(article: dict[str, Any]) -> float:
            body = article.get("body", "")
            title = article.get("title", "")
            score = 0.5
            words = len(body.split())
            if words > 300:
                score += 0.15
            elif words < 50:
                score -= 0.15
            if '"' in body or "said" in body.lower():
                score += 0.1
            clickbait = ["shocking", "you won't believe", "incredible", "amazing", "wow", "breaking"]
            if any(p in title.lower() for p in clickbait):
                score -= 0.2
            return max(0.0, min(1.0, score))

        def _novelty_score(article: dict[str, Any]) -> float:
            body_len = len((article.get("body") or "").split())
            length_score = min(1.0, body_len / 500)
            title = (article.get("title") or "").lower()
            generic = {"the", "a", "an", "update", "news", "report"}
            title_words = set(title.split())
            generic_ratio = len(title_words & generic) / max(1, len(title_words))
            title_score = 1.0 - generic_ratio
            cats = article.get("categories", [])
            cat_score = min(1.0, len(cats) / 3)
            return length_score * 0.4 + title_score * 0.35 + cat_score * 0.25

        scores: list[dict[str, Any]] = []
        for article in pool:
            aid = article["article_id"]
            for dimension, scorer in (
                ("relevance", _relevance_score),
                ("credibility", _credibility_score),
                ("novelty", _novelty_score),
            ):
                scores.append(
                    {
                        "article_id": aid,
                        "filter_id": filter_id,
                        "user_id": user_id,
                        "dimension": dimension,
                        "score": round(scorer(article), 4),
                        "scored_at": "",
                    }
                )
        return scores

    ##############################
    # Standing filter readiness
    ##############################

    async def _check_standing_filters(self, behaviour: CyclicBehaviour) -> None:
        cfg = self._config
        standing = await self._blackboard.get_standing_filters()
        for f in standing:
            fid = f["filter_id"]
            delivery = f.get("delivery", {})
            min_items = delivery.get("min_items_before_push", cfg.limit_min_items_before_push)
            min_interval_minutes = delivery.get("min_interval_minutes", cfg.limit_min_interval_minutes)
            breaking_threshold = delivery.get("breaking_threshold", cfg.score_breaking_threshold)

            state = self._standing_state.setdefault(
                fid,
                {
                    "last_push_at": None,
                    "accumulated_count": 0,
                    "pushed_article_ids": set(),
                },
            )

            # Only consider scores for articles we have NOT already pushed
            scores = await self._blackboard.get_scores_for_filter(fid)
            pushed_set: set[str] = state["pushed_article_ids"]
            new_scores = [s for s in scores if s.get("article_id") not in pushed_set]

            high_scores = [s for s in new_scores if s.get("score", 0) >= cfg.score_high_score]
            state["accumulated_count"] = len(high_scores)

            last_push = state["last_push_at"]
            now = datetime.now(timezone.utc)
            interval_ok = True
            if last_push:
                elapsed = (now - datetime.fromisoformat(last_push)).total_seconds() / 60
                interval_ok = elapsed >= min_interval_minutes

            # Breaking news: any single *new* article above threshold
            breaking = any(s.get("score", 0) >= breaking_threshold for s in new_scores)

            ready = breaking or (len(high_scores) >= min_items and interval_ok)

            if ready:
                user_id = f.get("user_id", "default_user")
                max_items = delivery.get("max_items", cfg.limit_bundle_max_items)
                bundle = await self._compose_bundle(fid, user_id, "standing_push", max_items)

                if bundle:
                    msg = Message(to=self._clerk_jid)
                    msg.set_metadata("performative", "inform")
                    msg.set_metadata("ontology", ONTOLOGY_EDITOR)
                    msg.body = json.dumps(BundleDeliveryMessage(**bundle).model_dump())
                    await behaviour.send(msg)
                    self.log.info(
                        "Pushed standing bundle %s for filter %s",
                        bundle["bundle_id"],
                        fid,
                    )

                    # Update watermark with pushed article IDs (cap to avoid unbounded growth)
                    pushed_ids = {a["article_id"] for a in bundle.get("articles", [])}
                    state["pushed_article_ids"].update(pushed_ids)
                    if len(state["pushed_article_ids"]) > cfg.limit_standing_push_ids:
                        # Drop oldest IDs by reinserting the most recent
                        state["pushed_article_ids"] = set(
                            list(state["pushed_article_ids"])[-cfg.limit_standing_push_ids :]
                        )

                    state["last_push_at"] = now.isoformat()
                    state["accumulated_count"] = 0

    ##############################
    # Message handling
    ##############################

    async def _handle_bundle_request(self, msg: Message, behaviour: CyclicBehaviour) -> None:
        try:
            req = BundleRequestMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid bundle request: %s", exc)
            return

        self.log.info("Handling bundle request %s for filter %s", req.request_id, req.filter_id)

        filter_ = await self._blackboard.get_filter(req.filter_id)
        if filter_ is None:
            fail = BundleFailureMessage(
                request_id=req.request_id,
                filter_id=req.filter_id,
                user_id=req.user_id,
                reason="Filter not found",
            )
            reply = Message(to=self._clerk_jid)
            reply.set_metadata("performative", "failure")
            reply.set_metadata("ontology", ONTOLOGY_EDITOR)
            reply.body = fail.model_dump_json()
            await behaviour.send(reply)
            return

        delivery = filter_.get("delivery", {})
        max_items = delivery.get("max_items", self._config.limit_bundle_max_items)
        bundle = await self._compose_bundle(req.filter_id, req.user_id, "one_off", max_items)

        if bundle:
            reply = Message(to=self._clerk_jid)
            reply.set_metadata("performative", "inform")
            reply.set_metadata("ontology", ONTOLOGY_EDITOR)
            reply.body = json.dumps(BundleDeliveryMessage(**bundle, request_id=req.request_id).model_dump())
            await behaviour.send(reply)
        else:
            fail = BundleFailureMessage(
                request_id=req.request_id,
                filter_id=req.filter_id,
                user_id=req.user_id,
                reason="No articles matched the filter",
            )
            reply = Message(to=self._clerk_jid)
            reply.set_metadata("performative", "failure")
            reply.set_metadata("ontology", ONTOLOGY_EDITOR)
            reply.body = fail.model_dump_json()
            await behaviour.send(reply)

    async def _handle_filter_registered(self, msg: Message) -> None:
        try:
            reg = FilterRegisteredMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid filter registration: %s", exc)
            return

        self.log.info("Registered filter %s (mode=%s)", reg.filter_id, reg.mode)

        if reg.mode == "standing":
            self._standing_state[reg.filter_id] = {
                "last_push_at": None,
                "accumulated_count": 0,
                "pushed_article_ids": set(),
            }

    async def _handle_filter_removed(self, msg: Message) -> None:
        try:
            rem = FilterRemovedMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid filter removal: %s", exc)
            return

        self._standing_state.pop(rem.filter_id, None)
        self.log.info("Removed filter %s from standing watch", rem.filter_id)

    async def _handle_source_health(self, msg: Message) -> None:
        try:
            health = SourceHealthMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid source health message: %s", exc)
            return

        self.log.info("Source %s health: %s (%s)", health.source_id, health.status, health.reason)

    ##############################
    # Behaviours
    ##############################

    class StandingWatchBehaviour(CyclicBehaviour):
        async def run(self) -> None:
            await self.agent._check_standing_filters(self)
            await asyncio.sleep(self.agent._config.interval_standing_watch)

    class MessageRouter(CyclicBehaviour):
        async def run(self) -> None:
            msg = await self.receive(timeout=1)
            if msg is None:
                return

            perf = (msg.get_metadata("performative") or "").lower()

            if perf == "request":
                await self.agent._handle_bundle_request(msg, self)
            elif perf == "inform":
                body = msg.body or "{}"
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    return

                msg_type = data.get("type")
                if msg_type == "filter_registered":
                    await self.agent._handle_filter_registered(msg)
                elif msg_type == "filter_removed":
                    await self.agent._handle_filter_removed(msg)
                elif msg_type == "source_health":
                    await self.agent._handle_source_health(msg)

    async def setup(self) -> None:
        self.log.info("EditorAgent %s starting...", self.jid)
        self.add_behaviour(self.StandingWatchBehaviour())
        self.add_behaviour(self.MessageRouter())
