"""Tests for the ClerkAgent (no SPADE runtime).

Exercises filter registration, bundle request/response flow via a mock
blackboard, feedback recording, and the bundle queue.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from sp1.agents.clerk.clerk import ClerkAgent
from sp1.agents.models.clerk_params import ClerkParams
from sp1.infra.blackboard import Blackboard
from sp1.infra.messages import BundleDeliveryMessage


def _make_clerk(blackboard: Blackboard) -> ClerkAgent:
    clerk = ClerkAgent(
        ClerkParams(
            jid="clerk@localhost",
            password="testpass",
            blackboard=blackboard,
            editor_jid="editor@localhost",
            user_id="ui_user",
            session_timeout_seconds=3600,
        )
    )
    # Unit tests don't run SPADE agent lifecycle, so mock the sender behaviour
    clerk._sender = AsyncMock()
    return clerk


class TestClerkFilterRegistration:
    @pytest.mark.asyncio
    async def test_register_filter_writes_to_blackboard(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        fid = await clerk.register_filter(keywords=["GPT", "AI"], mode="one_off")
        assert fid.startswith("filter_")
        filters = await bb.get_all_filters()
        assert len(filters) == 1
        assert filters[0]["keywords"] == ["GPT", "AI"]

    @pytest.mark.asyncio
    async def test_register_filter_includes_delivery(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        fid = await clerk.register_filter(
            keywords=["climate"],
            mode="standing",
            delivery={"max_items": 3},
        )
        f = await bb.get_filter(fid)
        assert f is not None
        assert f["mode"] == "standing"
        assert f["delivery"]["max_items"] == 3

    @pytest.mark.asyncio
    async def test_remove_filter(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        fid = await clerk.register_filter(keywords=["quantum"], mode="one_off")
        await clerk.remove_filter(fid)
        f = await bb.get_filter(fid)
        assert f is None


class TestClerkFeedback:
    @pytest.mark.asyncio
    async def test_submit_feedback(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        await clerk.submit_feedback("article_123", "filter_1", True, notes="Good read")
        history = await bb.get_feedback_history("ui_user")
        assert len(history) == 1
        assert history[0]["article_id"] == "article_123"
        assert history[0]["relevant"] is True


class TestClerkBundleDelivery:
    @pytest.mark.asyncio
    async def test_handle_bundle_delivery_puts_to_queue(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        bundle = BundleDeliveryMessage(
            bundle_id="b1",
            filter_id="f1",
            user_id="ui_user",
            trigger="standing_push",
            articles=[
                {
                    "article_id": "a1",
                    "source_id": "src",
                    "title": "Title",
                    "url": "http://example.com",
                    "summary": "Summary",
                    "scores": {"aggregated": 0.8},
                }
            ],
        )
        from spade.message import Message

        msg = Message()
        msg.body = bundle.model_dump_json()
        await clerk._handle_bundle_delivery(msg)

        result = await clerk.get_next_bundle(timeout=0.5)
        assert result is not None
        assert result["bundle_id"] == "b1"
        assert len(result["articles"]) == 1

    @pytest.mark.asyncio
    async def test_get_next_bundle_timeout_empty(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        result = await clerk.get_next_bundle(timeout=0.1)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_bundle_failure(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        from spade.message import Message

        from sp1.infra.messages import BundleFailureMessage

        fail = BundleFailureMessage(
            request_id="r1",
            filter_id="f1",
            user_id="ui_user",
            reason="No articles",
        )
        msg = Message()
        msg.body = fail.model_dump_json()
        # Should not raise
        await clerk._handle_bundle_failure(msg)


class TestClerkSuggestions:
    @pytest.mark.asyncio
    async def test_generate_suggestions_narrowing(self) -> None:
        bb = Blackboard()
        clerk = _make_clerk(bb)
        await clerk.register_filter(keywords=["tech"], mode="standing")
        # Simulate many deliveries but little feedback
        for i in range(25):
            await bb.record_delivery("ui_user", f"article_{i}", f"bundle_{i}")
        await clerk._generate_suggestions()
        suggestion = await clerk._pending_suggestions.get()
        assert suggestion["type"] == "suggestion"
        assert "narrowing" in suggestion["message"].lower() or "feedback" in suggestion["message"].lower()
