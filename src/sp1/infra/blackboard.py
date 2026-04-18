from __future__ import annotations

import asyncio
from typing import Any


class Blackboard:
    """Thread/async-safe shared memory for candidate articles and source health."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._candidate_pool: list[dict[str, Any]] = []
        self._source_health_flags: dict[str, dict[str, str]] = {}
        self._score_board: dict[str, dict[str, Any]] = {}
        self._filter_registry: dict[str, dict[str, Any]] = {}
        self._user_profiles: dict[str, dict[str, Any]] = {}
        self._source_reputation: dict[str, float] = {}
        self._pending_delivery_queue: dict[str, list[dict[str, Any]]] = {}

    async def add_articles(self, articles: list[dict[str, Any]]) -> None:
        async with self._lock:
            self._candidate_pool.extend(articles)

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

    async def snapshot_candidate_pool(self) -> list[dict[str, Any]]:
        """Return a shallow copy of all articles in the candidate pool (for inspection / persistence)."""
        async with self._lock:
            return list(self._candidate_pool)

    async def write_score_vector(self, vector: dict[str, Any]) -> None:
        key = f"{vector['article_id']}:{vector.get('filter_id', '')}"
        async with self._lock:
            self._score_board[key] = dict(vector)

    async def get_scores_for_article(self, article_id: str) -> list[dict[str, Any]]:
        prefix = f"{article_id}:"
        async with self._lock:
            return [dict(v) for k, v in self._score_board.items() if k.startswith(prefix)]

    async def snapshot_score_board(self) -> dict[str, dict[str, Any]]:
        async with self._lock:
            return {k: dict(v) for k, v in self._score_board.items()}

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

    async def upsert_user_profile(self, profile: dict[str, Any]) -> None:
        uid = profile["user_id"]
        async with self._lock:
            self._user_profiles[uid] = dict(profile)

    async def get_user_profile(self, user_id: str) -> dict[str, Any] | None:
        async with self._lock:
            entry = self._user_profiles.get(user_id)
            return dict(entry) if entry is not None else None

    async def update_source_reputation(self, source_id: str, score: float) -> None:
        async with self._lock:
            self._source_reputation[source_id] = score

    async def get_source_reputation(self, source_id: str) -> float | None:
        async with self._lock:
            return self._source_reputation.get(source_id)

    async def snapshot_source_reputation(self) -> dict[str, float]:
        async with self._lock:
            return dict(self._source_reputation)

    async def enqueue_delivery(self, user_id: str, bundle: dict[str, Any]) -> None:
        async with self._lock:
            self._pending_delivery_queue.setdefault(user_id, []).append(dict(bundle))

    async def dequeue_deliveries(self, user_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            queued = self._pending_delivery_queue.pop(user_id, [])
            return list(queued)
