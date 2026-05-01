import asyncio

import pytest

from sp1.infra.blackboard import Blackboard


def test_real_blackboard_snapshot() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.add_articles([{"article_id": "1"}])
        snap = await bb.snapshot_candidate_pool()
        assert len(snap) == 1
        assert snap[0]["article_id"] == "1"

    asyncio.run(_run())


def test_score_board_write_and_read() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.write_score_vector({"article_id": "a1", "filter_id": "f1", "score": 0.7})
        scores = await bb.get_scores_for_article("a1")
        assert len(scores) == 1
        assert scores[0]["article_id"] == "a1"
        assert scores[0]["filter_id"] == "f1"
        assert scores[0]["score"] == 0.7

    asyncio.run(_run())


def test_score_board_overwrite() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.write_score_vector({"article_id": "a1", "filter_id": "f1", "score": 0.1})
        await bb.write_score_vector({"article_id": "a1", "filter_id": "f1", "score": 0.9})
        scores = await bb.get_scores_for_article("a1")
        assert len(scores) == 1
        assert scores[0]["score"] == 0.9

    asyncio.run(_run())


def test_score_board_snapshot() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.write_score_vector({"article_id": "a1", "filter_id": "f1", "score": 1.0})
        await bb.write_score_vector({"article_id": "a2", "filter_id": "f1", "score": 2.0})
        snap = await bb.snapshot_score_board()
        assert len(snap) == 2

    asyncio.run(_run())


def test_filter_registry_register_and_get() -> None:
    async def _run() -> None:
        bb = Blackboard()
        f = {"filter_id": "f1", "keywords": ["x"]}
        await bb.register_filter(f)
        got = await bb.get_filter("f1")
        assert got == f
        all_f = await bb.get_all_filters()
        assert len(all_f) == 1
        assert all_f[0]["filter_id"] == "f1"

    asyncio.run(_run())


def test_filter_registry_update() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.register_filter({"filter_id": "f1", "keywords": ["a"]})
        await bb.update_filter("f1", {"filter_id": "f1", "keywords": ["b", "c"]})
        got = await bb.get_filter("f1")
        assert got is not None
        assert got["keywords"] == ["b", "c"]

    asyncio.run(_run())


def test_filter_registry_remove() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.register_filter({"filter_id": "f1", "keywords": ["a"]})
        await bb.remove_filter("f1")
        assert await bb.get_filter("f1") is None
        assert await bb.get_all_filters() == []

    asyncio.run(_run())


def test_filter_registry_register_duplicate_raises() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.register_filter({"filter_id": "f1", "keywords": ["a"]})
        with pytest.raises(KeyError):
            await bb.register_filter({"filter_id": "f1", "keywords": ["b"]})

    asyncio.run(_run())


def test_filter_registry_update_missing_raises() -> None:
    async def _run() -> None:
        bb = Blackboard()
        with pytest.raises(KeyError):
            await bb.update_filter("missing", {"filter_id": "missing", "keywords": []})

    asyncio.run(_run())


def test_filter_registry_remove_missing_raises() -> None:
    async def _run() -> None:
        bb = Blackboard()
        with pytest.raises(KeyError):
            await bb.remove_filter("missing")

    asyncio.run(_run())


def test_user_profile_upsert_and_get() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.upsert_user_profile({"user_id": "u1", "name": "Alice"})
        p = await bb.get_user_profile("u1")
        assert p is not None
        assert p["user_id"] == "u1"
        assert p["name"] == "Alice"

    asyncio.run(_run())


def test_user_profile_overwrite() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.upsert_user_profile({"user_id": "u1", "preferences": {"theme": "dark"}})
        await bb.upsert_user_profile({"user_id": "u1", "preferences": {"theme": "light"}})
        p = await bb.get_user_profile("u1")
        assert p is not None
        assert p["preferences"]["theme"] == "light"

    asyncio.run(_run())


def test_user_profile_get_unknown() -> None:
    async def _run() -> None:
        bb = Blackboard()
        assert await bb.get_user_profile("nobody") is None

    asyncio.run(_run())


def test_source_reputation_update_and_get() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.update_source_reputation("reuters", 0.8)
        assert await bb.get_source_reputation("reuters") == 0.8

    asyncio.run(_run())


def test_source_reputation_get_unknown() -> None:
    async def _run() -> None:
        bb = Blackboard()
        assert await bb.get_source_reputation("unknown") is None

    asyncio.run(_run())


def test_source_reputation_snapshot() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.update_source_reputation("a", 0.1)
        await bb.update_source_reputation("b", 0.2)
        snap = await bb.snapshot_source_reputation()
        assert snap == {"a": 0.1, "b": 0.2}

    asyncio.run(_run())


def test_pending_delivery_enqueue_dequeue() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.enqueue_delivery("u1", {"id": 1})
        await bb.enqueue_delivery("u1", {"id": 2})
        first = await bb.dequeue_deliveries("u1")
        assert first == [{"id": 1}, {"id": 2}]
        second = await bb.dequeue_deliveries("u1")
        assert second == []

    asyncio.run(_run())


def test_pending_delivery_dequeue_unknown_user() -> None:
    async def _run() -> None:
        bb = Blackboard()
        assert await bb.dequeue_deliveries("unknown") == []

    asyncio.run(_run())


def test_source_health_snapshot() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.update_source_health("s1", "healthy", "")
        await bb.update_source_health("s2", "unavailable", "down")
        snap = await bb.snapshot_source_health()
        assert len(snap) == 2
        assert snap["s1"]["status"] == "healthy"
        assert snap["s2"]["reason"] == "down"

    asyncio.run(_run())


def test_get_source_health_unknown() -> None:
    async def _run() -> None:
        bb = Blackboard()
        assert await bb.get_source_health("missing") is None

    asyncio.run(_run())


def test_message_log() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.log_message("sender1", "receiver1", "inform", "hello world")
        await bb.log_message("sender2", "receiver2", "request", "get data")
        logs = await bb.snapshot_message_log(limit=10)
        assert len(logs) == 2
        assert logs[0]["sender"] == "sender1"
        assert logs[0]["performative"] == "inform"
        assert logs[1]["body_preview"] == "get data"

    asyncio.run(_run())


def test_bundle_registry_record_and_get() -> None:
    async def _run() -> None:
        bb = Blackboard()
        bundle = {"bundle_id": "b1", "filter_id": "f1", "articles": [{"title": "Test"}]}
        await bb.record_bundle(bundle)
        retrieved = await bb.get_bundle("b1")
        assert retrieved is not None
        assert retrieved["bundle_id"] == "b1"
        assert retrieved["filter_id"] == "f1"

    asyncio.run(_run())


def test_bundle_registry_maxlen_eviction() -> None:
    async def _run() -> None:
        bb = Blackboard()
        # Override maxlen to a small number for testing
        bb._bundle_registry_maxlen = 3
        for i in range(5):
            await bb.record_bundle({"bundle_id": f"b{i}", "filter_id": "f1", "articles": []})
        snapshot = await bb.snapshot_bundle_registry()
        assert len(snapshot) == 3
        # Oldest (b0, b1) should have been evicted
        ids = {b["bundle_id"] for b in snapshot}
        assert "b0" not in ids
        assert "b1" not in ids
        assert "b4" in ids

    asyncio.run(_run())


def test_bundle_registry_filter_lookup() -> None:
    async def _run() -> None:
        bb = Blackboard()
        await bb.record_bundle({"bundle_id": "b1", "filter_id": "f1", "articles": []})
        await bb.record_bundle({"bundle_id": "b2", "filter_id": "f2", "articles": []})
        await bb.record_bundle({"bundle_id": "b3", "filter_id": "f1", "articles": []})
        f1_bundles = await bb.get_bundles_for_filter("f1")
        assert len(f1_bundles) == 2
        assert {b["bundle_id"] for b in f1_bundles} == {"b1", "b3"}

    asyncio.run(_run())
