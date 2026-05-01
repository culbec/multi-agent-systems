from __future__ import annotations

import asyncio
import json
import pathlib
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from sp1.infra.config import SP1Config


class Blackboard:
    """Thread/async-safe shared memory for candidate articles and source health.

    Supports JSON persistence so the system can resume across restarts.
    """

    def __init__(self, max_pool_size: int | None = None) -> None:
        self._config = SP1Config()
        self._lock = asyncio.Lock()
        self._max_pool_size = max_pool_size if max_pool_size is not None else self._config.limit_pool_size
        self._candidate_pool: list[dict[str, Any]] = []
        self._source_health_flags: dict[str, dict[str, str]] = {}
        self._score_board: dict[str, dict[str, Any]] = {}
        self._filter_registry: dict[str, dict[str, Any]] = {}
        self._user_profiles: dict[str, dict[str, Any]] = {}
        self._source_reputation: dict[str, float] = {}
        self._pending_delivery_queue: dict[str, list[dict[str, Any]]] = {}
        self._delivery_history: dict[str, list[dict[str, Any]]] = {}
        self._feedback_history: dict[str, list[dict[str, Any]]] = {}
        self._message_log: deque[dict[str, Any]] = deque(maxlen=self._config.message_log_maxlen)
        self._bundle_registry: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._bundle_registry_maxlen = self._config.bundle_registry_maxlen

    ##############################
    # Candidate Pool
    ##############################

    async def add_articles(self, articles: list[dict[str, Any]]) -> None:
        async with self._lock:
            self._candidate_pool.extend(articles)
            if len(self._candidate_pool) > self._max_pool_size:
                self._candidate_pool = self._candidate_pool[-self._max_pool_size :]

    async def snapshot_candidate_pool(self) -> list[dict[str, Any]]:
        """Return a shallow copy of all articles in the candidate pool."""
        async with self._lock:
            return list(self._candidate_pool)

    async def get_articles_for_filter(self, f: dict[str, Any]) -> list[dict[str, Any]]:
        """Return articles from the candidate pool that match a filter.

        Matching is done by keywords (title/body), categories, sources, and
        max_age_hours. Keyword matching uses **whole-word** matching via regex
        word boundaries so that a keyword like ``"gpt"`` does not match inside
        unrelated words (e.g. ``"trump"``).
        """
        import re

        async with self._lock:
            keywords = [k.lower() for k in f.get("keywords", [])]
            keyword_mode = f.get("keyword_mode", "any")
            categories = [c.lower() for c in f.get("categories", [])]
            sources = f.get("sources", [])
            max_age_hours = f.get("max_age_hours")
            cutoff: datetime | None = None
            if max_age_hours is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

            results: list[dict[str, Any]] = []
            for article in self._candidate_pool:
                # Age filter
                if cutoff is not None:
                    age_str = article.get("published_at") or article.get("fetched_at")
                    if age_str:
                        try:
                            age_dt = datetime.fromisoformat(age_str)
                            # Make naive timezone-aware for comparison
                            if age_dt.tzinfo is None:
                                age_dt = age_dt.replace(tzinfo=timezone.utc)
                            if age_dt < cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass  # fail-open on unparseable timestamps

                title = (article.get("title") or "").lower()
                body = (article.get("body") or "").lower()
                summary = (article.get("summary") or "").lower()
                text = f"{title} {body} {summary}"

                # Keyword matching (whole-word)
                if keywords:

                    def _matches(kw: str) -> bool:
                        # Multi-word → phrase match; single-word → \b boundary
                        if " " in kw:
                            return kw in text
                        pattern = r"\b" + re.escape(kw) + r"\b"
                        return bool(re.search(pattern, text))

                    matches = [_matches(k) for k in keywords]
                    if keyword_mode == "all" and not all(matches):
                        continue
                    if keyword_mode == "any" and not any(matches):
                        continue

                # Category matching
                art_cats = [c.lower() for c in article.get("categories", [])]
                if categories and not any(c in art_cats for c in categories):
                    continue

                # Source matching
                if sources and article.get("source_id") not in sources:
                    continue

                results.append(dict(article))

            return results

    async def clear_candidate_pool(self) -> None:
        """Remove all articles from the candidate pool (useful for testing)."""
        async with self._lock:
            self._candidate_pool.clear()

    ##############################
    # Source Health
    ##############################

    async def update_source_health(self, source_id: str, status: str, reason: str = "") -> None:
        async with self._lock:
            self._source_health_flags[source_id] = {"status": status, "reason": reason}

    async def get_source_health(self, source_id: str) -> dict[str, str] | None:
        async with self._lock:
            entry = self._source_health_flags.get(source_id)
            return dict(entry) if entry is not None else None

    async def snapshot_source_health(self) -> dict[str, dict[str, str]]:
        async with self._lock:
            return {k: dict(v) for k, v in self._source_health_flags.items()}

    ##############################
    # Score Board
    ##############################

    async def write_score_vector(self, vector: dict[str, Any]) -> None:
        key = f"{vector['article_id']}:{vector.get('filter_id', '')}:{vector.get('dimension', '')}"
        async with self._lock:
            self._score_board[key] = dict(vector)

    async def get_scores_for_article(self, article_id: str) -> list[dict[str, Any]]:
        prefix = f"{article_id}:"
        async with self._lock:
            return [dict(v) for k, v in self._score_board.items() if k.startswith(prefix)]

    async def get_scores_for_filter(self, filter_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(v) for k, v in self._score_board.items() if f":{filter_id}:" in k]

    async def snapshot_score_board(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return {k: dict(v) for k, v in self._score_board.items()}

    async def clear_score_board(self) -> None:
        async with self._lock:
            self._score_board.clear()

    ##############################
    # Filter Registry
    ##############################

    async def register_filter(self, f: dict[str, Any]) -> None:
        fid = f["filter_id"]
        async with self._lock:
            if fid in self._filter_registry:
                raise KeyError(fid)
            self._filter_registry[fid] = dict(f)

    async def update_filter(self, filter_id: str, f: dict[str, Any]) -> None:
        async with self._lock:
            if filter_id not in self._filter_registry:
                raise KeyError(filter_id)
            self._filter_registry[filter_id] = dict(f)

    async def remove_filter(self, filter_id: str) -> None:
        async with self._lock:
            if filter_id not in self._filter_registry:
                raise KeyError(filter_id)
            del self._filter_registry[filter_id]

    async def get_filter(self, filter_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._filter_registry.get(filter_id)
            return dict(entry) if entry is not None else None

    async def get_all_filters(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(v) for v in self._filter_registry.values()]

    async def get_standing_filters(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(v) for v in self._filter_registry.values() if v.get("mode") == "standing"]

    ##############################
    # User Profiles
    ##############################

    async def upsert_user_profile(self, profile: dict[str, Any]) -> None:
        uid = profile["user_id"]
        async with self._lock:
            self._user_profiles[uid] = dict(profile)

    async def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._user_profiles.get(user_id)
            return dict(entry) if entry is not None else None

    async def get_all_user_profiles(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return {k: dict(v) for k, v in self._user_profiles.items()}

    ##############################
    # Source Reputation
    ##############################

    async def update_source_reputation(self, source_id: str, score: float) -> None:
        async with self._lock:
            self._source_reputation[source_id] = score

    async def get_source_reputation(self, source_id: str) -> float | None:
        async with self._lock:
            return self._source_reputation.get(source_id)

    async def snapshot_source_reputation(self) -> dict[str, float]:
        async with self._lock:
            return dict(self._source_reputation)

    ##############################
    # Pending Delivery Queue
    ##############################

    async def enqueue_delivery(self, user_id: str, bundle: dict[str, Any]) -> None:
        async with self._lock:
            self._pending_delivery_queue.setdefault(user_id, []).append(dict(bundle))

    async def dequeue_deliveries(self, user_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            queued = self._pending_delivery_queue.pop(user_id, [])
            return list(queued)

    async def snapshot_pending_deliveries(self) -> dict[str, list[dict[str, Any]]]:
        async with self._lock:
            return {k: [dict(b) for b in v] for k, v in self._pending_delivery_queue.items()}

    ##############################
    # Delivery History
    ##############################

    async def record_delivery(self, user_id: str, article_id: str, bundle_id: str) -> None:
        async with self._lock:
            self._delivery_history.setdefault(user_id, []).append(
                {
                    "article_id": article_id,
                    "bundle_id": bundle_id,
                    "delivered_at": "",
                }
            )

    async def get_delivery_history(self, user_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._delivery_history.get(user_id, []))

    ##############################
    # Feedback History
    ##############################

    async def record_feedback(self, feedback: dict[str, Any]) -> None:
        user_id = feedback["user_id"]
        async with self._lock:
            self._feedback_history.setdefault(user_id, []).append(dict(feedback))

    async def get_feedback_history(self, user_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._feedback_history.get(user_id, []))

    ##############################
    # Message Log
    ##############################

    async def log_message(
        self,
        sender: str,
        receiver: str,
        performative: str,
        body_preview: str,
    ) -> None:
        async with self._lock:
            self._message_log.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sender": sender,
                    "receiver": receiver,
                    "performative": performative,
                    "body_preview": body_preview,
                }
            )

    async def snapshot_message_log(self, limit: int = 200) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._message_log)[-limit:]

    ##############################
    # Bundle Registry
    ##############################

    async def record_bundle(self, bundle: dict[str, Any]) -> None:
        bid = bundle.get("bundle_id")
        if not bid:
            return
        async with self._lock:
            self._bundle_registry[bid] = dict(bundle)
            # Evict oldest bundles if over limit
            while len(self._bundle_registry) > self._bundle_registry_maxlen:
                self._bundle_registry.popitem(last=False)

    async def get_bundle(self, bundle_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._bundle_registry.get(bundle_id)
            return dict(entry) if entry is not None else None

    async def get_bundles_for_filter(self, filter_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(b) for b in self._bundle_registry.values() if b.get("filter_id") == filter_id]

    async def snapshot_bundle_registry(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [dict(b) for b in self._bundle_registry.values()]

    ##############################
    # Persistence
    ##############################

    async def save_to_json(self, path: str | pathlib.Path) -> None:
        """Persist the entire blackboard state to a JSON file."""
        async with self._lock:
            payload = {
                "candidate_pool": list(self._candidate_pool),
                "source_health_flags": {k: dict(v) for k, v in self._source_health_flags.items()},
                "score_board": {k: dict(v) for k, v in self._score_board.items()},
                "filter_registry": {k: dict(v) for k, v in self._filter_registry.items()},
                "user_profiles": {k: dict(v) for k, v in self._user_profiles.items()},
                "source_reputation": dict(self._source_reputation),
                "pending_delivery_queue": {k: [dict(b) for b in v] for k, v in self._pending_delivery_queue.items()},
                "delivery_history": {k: [dict(b) for b in v] for k, v in self._delivery_history.items()},
                "feedback_history": {k: [dict(b) for b in v] for k, v in self._feedback_history.items()},
            }

        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    async def load_from_json(self, path: str | pathlib.Path) -> None:
        """Restore blackboard state from a JSON file."""
        p = pathlib.Path(path)
        if not p.exists():
            return

        with open(p, "r", encoding="utf-8") as f:
            payload = json.load(f)

        async with self._lock:
            self._candidate_pool = list(payload.get("candidate_pool", []))
            self._source_health_flags = {k: dict(v) for k, v in payload.get("source_health_flags", {}).items()}
            self._score_board = {k: dict(v) for k, v in payload.get("score_board", {}).items()}
            self._filter_registry = {k: dict(v) for k, v in payload.get("filter_registry", {}).items()}
            self._user_profiles = {k: dict(v) for k, v in payload.get("user_profiles", {}).items()}
            self._source_reputation = dict(payload.get("source_reputation", {}))
            self._pending_delivery_queue = {
                k: [dict(b) for b in v] for k, v in payload.get("pending_delivery_queue", {}).items()
            }
            self._delivery_history = {k: [dict(b) for b in v] for k, v in payload.get("delivery_history", {}).items()}
            self._feedback_history = {k: [dict(b) for b in v] for k, v in payload.get("feedback_history", {}).items()}
