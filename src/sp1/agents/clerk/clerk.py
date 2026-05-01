from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour, PeriodicBehaviour
from spade.message import Message

from sp1.agents.models.clerk_params import ClerkParams
from sp1.infra.config import SP1Config
from sp1.infra.messages import (
    BundleDeliveryMessage,
    BundleFailureMessage,
    BundleRequestMessage,
    FilterRegisteredMessage,
    FilterRemovedMessage,
)
from sp1.infra.ontology import ONTOLOGY_CLERK
from sp1.utils.logger import get_logger


class ClerkAgent(Agent):
    """Sole user-facing agent.

    Responsibilities:
    * Parse/validate user filter declarations and register them on the blackboard.
    * Notify the Editor of filter changes.
    * Receive composed bundles from the Editor and deliver them to the user.
    * Queue deliveries for offline users and deliver on reconnect.
    * Solicit feedback after meaningful deliveries.
    * Pro-actively suggest filter adjustments.
    """

    def __init__(self, params: ClerkParams) -> None:
        super().__init__(params.jid, params.password)
        self.log = get_logger(str(self.jid))
        self._config = SP1Config()
        self._blackboard = params.blackboard
        self._editor_jid = params.editor_jid
        self._user_id = params.user_id
        self._session_timeout_seconds = params.session_timeout_seconds

        # Session state
        self._session_active: bool = True
        self._last_activity_at: datetime = datetime.now(timezone.utc)

        # Pending callbacks for UI / CLI integration
        self._pending_bundles: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending_suggestions: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        # Dedicated sender behaviour for agent-level send() calls
        self._sender: CyclicBehaviour | None = None

    ##############################
    # Agent-level send helper
    ##############################

    async def _send(self, msg: Message) -> None:
        """Send *msg* using the dedicated sender behaviour.

        SPADE v4's ``send()`` is a ``Behaviour`` method, not an ``Agent``
        method.  We keep a lightweight ``SenderBehaviour`` alive precisely
        so agent-level code can dispatch messages.
        """
        if self._sender is None:
            raise RuntimeError("Clerk agent not ready for sending (no sender behaviour)")
        await self._sender.send(msg)

    ##############################
    # Filter management
    ##############################

    async def register_filter(
        self,
        keywords: list[str],
        mode: str = "one_off",
        categories: list[str] | None = None,
        sources: list[str] | None = None,
        max_age_hours: int | None = None,
        min_credibility: float | None = None,
        delivery: dict[str, Any] | None = None,
        keyword_mode: str = "any",
    ) -> str:
        """Register a new filter, write it to the blackboard, and notify the Editor.

        :return: The generated ``filter_id``.
        """
        filter_id = f"filter_{uuid.uuid4().hex[:8]}"
        f: dict[str, Any] = {
            "filter_id": filter_id,
            "user_id": self._user_id,
            "mode": mode,
            "keywords": keywords,
            "keyword_mode": keyword_mode,
            "categories": categories or [],
            "sources": sources or [],
            "max_age_hours": max_age_hours,
            "min_credibility": min_credibility,
            "delivery": delivery or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_push_at": None,
        }

        await self._blackboard.register_filter(f)
        self.log.info("Registered filter %s (mode=%s, keywords=%s)", filter_id, mode, keywords)

        # Notify Editor
        msg = Message(to=self._editor_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", ONTOLOGY_CLERK)
        msg.body = FilterRegisteredMessage(**f).model_dump_json()
        await self._send(msg)

        return filter_id

    async def remove_filter(self, filter_id: str) -> None:
        """Remove a filter and notify the Editor."""
        await self._blackboard.remove_filter(filter_id)
        self.log.info("Removed filter %s", filter_id)

        msg = Message(to=self._editor_jid)
        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", ONTOLOGY_CLERK)
        msg.body = FilterRemovedMessage(filter_id=filter_id, user_id=self._user_id).model_dump_json()
        await self._send(msg)

    async def request_bundle(self, filter_id: str) -> dict[str, Any] | None:
        """Send a synchronous bundle request to the Editor and wait for the response.

        :return: The bundle dict, or ``None`` on failure / timeout.
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        msg = Message(to=self._editor_jid)
        msg.set_metadata("performative", "request")
        msg.set_metadata("ontology", ONTOLOGY_CLERK)
        msg.body = BundleRequestMessage(
            request_id=request_id,
            filter_id=filter_id,
            user_id=self._user_id,
        ).model_dump_json()

        await self._send(msg)
        self.log.info("Sent bundle request %s for filter %s", request_id, filter_id)

        # Use a temporary OneShotBehaviour to receive the reply
        receiver = self._BundleReplyReceiver(request_id=request_id)
        self.add_behaviour(receiver)

        try:
            bundle = await asyncio.wait_for(receiver.wait_for_reply(), timeout=self._config.timeout_bundle_request)
            return bundle
        except asyncio.TimeoutError:
            self.log.warning("Bundle request %s timed out", request_id)
            return None
        finally:
            with contextlib.suppress(Exception):
                receiver.kill()

    ##############################
    # Feedback
    ##############################

    async def submit_feedback(self, article_id: str, filter_id: str, relevant: bool, notes: str = "") -> None:
        """Record user feedback and write it to the blackboard."""
        feedback = {
            "user_id": self._user_id,
            "article_id": article_id,
            "filter_id": filter_id,
            "relevant": relevant,
            "notes": notes,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._blackboard.record_feedback(feedback)
        self.log.info("Recorded feedback for article %s: relevant=%s", article_id, relevant)

    ##############################
    # Bundle delivery
    ##############################

    async def _handle_bundle_delivery(self, msg: Message) -> None:
        try:
            bundle = BundleDeliveryMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid bundle delivery: %s", exc)
            return

        bundle_user_id = bundle.user_id
        if bundle_user_id != self._user_id:
            self.log.warning(
                "Bundle user_id mismatch: expected %s, got %s (bundle=%s)",
                self._user_id,
                bundle_user_id,
                bundle.bundle_id,
            )

        self.log.info(
            "Received bundle %s (trigger=%s) with %d articles",
            bundle.bundle_id,
            bundle.trigger,
            len(bundle.articles),
        )

        # Record delivery in blackboard
        for art in bundle.articles:
            await self._blackboard.record_delivery(bundle_user_id, art["article_id"], bundle.bundle_id)

        # Record bundle for later query
        await self._blackboard.record_bundle(bundle.model_dump())

        # If session is active, deliver immediately; otherwise queue
        if self._session_active:
            await self._pending_bundles.put(bundle.model_dump())
        else:
            await self._blackboard.enqueue_delivery(bundle_user_id, bundle.model_dump())
            self.log.info("Queued bundle %s for offline user %s", bundle.bundle_id, bundle_user_id)

        # Update last activity
        self._last_activity_at = datetime.now(timezone.utc)

    async def _handle_bundle_failure(self, msg: Message) -> None:
        try:
            failure = BundleFailureMessage.model_validate_json(msg.body)
        except Exception as exc:
            self.log.warning("Invalid bundle failure: %s", exc)
            return

        self.log.warning("Bundle failure for filter %s: %s", failure.filter_id, failure.reason)

    async def get_next_bundle(self, timeout: float = 0.5) -> dict[str, Any] | None:
        """Non-blocking retrieval of the next pending bundle.

        :param timeout: seconds to wait before returning ``None`` if queue is empty.
        :return: bundle dict or ``None``.
        """
        try:
            return await asyncio.wait_for(self._pending_bundles.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def _generate_suggestions(self) -> None:
        """Periodically inspect standing filters and suggest adjustments."""
        filters = await self._blackboard.get_all_filters()
        for f in filters:
            if f.get("mode") != "standing":
                continue

            delivery_history = await self._blackboard.get_delivery_history(self._user_id)
            feedback_history = await self._blackboard.get_feedback_history(self._user_id)

            # Simple heuristic: if many articles delivered but low feedback, suggest narrowing
            cfg = self._config
            if len(delivery_history) > cfg.suggestion_delivery_threshold and len(feedback_history) < cfg.suggestion_feedback_threshold:
                suggestion = {
                    "type": "suggestion",
                    "filter_id": f["filter_id"],
                    "message": (
                        "You've received many articles but provided little feedback. "
                        "Consider narrowing your keywords or adding categories."
                    ),
                }
                await self._pending_suggestions.put(suggestion)
                self.log.info("Suggestion queued for filter %s", f["filter_id"])

    ##############################
    # Session management
    ##############################

    async def _check_session_timeout(self) -> None:
        now = datetime.now(timezone.utc)
        elapsed = (now - self._last_activity_at).total_seconds()
        if elapsed > self._session_timeout_seconds and self._session_active:
            self._session_active = False
            self.log.info("Session timed out for user %s", self._user_id)

    def activate_session(self) -> None:
        """Mark the session as active (e.g. on user login or UI interaction)."""
        self._session_active = True
        self._last_activity_at = datetime.now(timezone.utc)
        self.log.info("Session activated for user %s", self._user_id)

    ##############################
    # Behaviours
    ##############################

    class SenderBehaviour(CyclicBehaviour):
        """Lightweight behaviour that exists solely to provide ``send()`` to the agent."""

        async def run(self) -> None:
            await asyncio.sleep(3600)

    class _BundleReplyReceiver(OneShotBehaviour):
        """Temporary behaviour that captures a single reply to a bundle request."""

        def __init__(self, request_id: str) -> None:
            super().__init__()
            self._request_id = request_id
            # Create the future immediately (we are inside an async call-chain
            # so a running loop is guaranteed).
            self._future = asyncio.get_running_loop().create_future()

        async def run(self) -> None:
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                reply = await self.receive(timeout=2)
                if reply is None:
                    continue

                perf = (reply.get_metadata("performative") or "").lower()
                if perf == "inform":
                    try:
                        bundle = BundleDeliveryMessage.model_validate_json(reply.body)
                        if bundle.request_id is not None and bundle.request_id != self._request_id:
                            self.agent.log.debug(
                                "Ignoring bundle delivery with mismatched request_id: got=%s expected=%s",
                                bundle.request_id,
                                self._request_id,
                            )
                            continue
                        if not self._future.done():
                            self._future.set_result(bundle.model_dump())
                        return
                    except Exception as exc:
                        self.agent.log.warning("Invalid bundle delivery: %s", exc)
                        continue
                elif perf == "failure":
                    try:
                        failure = BundleFailureMessage.model_validate_json(reply.body)
                        if failure.request_id is not None and failure.request_id != self._request_id:
                            self.agent.log.debug(
                                "Ignoring bundle failure with mismatched request_id: got=%s expected=%s",
                                failure.request_id,
                                self._request_id,
                            )
                            continue
                        self.agent.log.warning("Bundle request failed: %s", failure.reason)
                    except Exception:
                        pass
                    if not self._future.done():
                        self._future.set_result(None)
                    return

            if not self._future.done():
                self._future.set_result(None)

        async def wait_for_reply(self) -> dict[str, Any] | None:
            return await self._future

    class IncomingMessageHandler(CyclicBehaviour):
        async def run(self) -> None:
            msg = await self.receive(timeout=1)
            if msg is None:
                return

            perf = (msg.get_metadata("performative") or "").lower()

            if perf == "inform":
                body = msg.body or "{}"
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    return

                msg_type = data.get("type")
                if msg_type == "bundle_delivery":
                    await self.agent._handle_bundle_delivery(msg)
                elif msg_type == "bundle_failure":
                    await self.agent._handle_bundle_failure(msg)

    class SessionTimeoutChecker(PeriodicBehaviour):
        async def run(self) -> None:
            await self.agent._check_session_timeout()

    class SuggestionGenerator(PeriodicBehaviour):
        async def run(self) -> None:
            await self.agent._generate_suggestions()

    async def setup(self) -> None:
        self.log.info("ClerkAgent %s starting for user %s...", self.jid, self._user_id)
        self._sender = self.SenderBehaviour()
        self.add_behaviour(self._sender)
        self.add_behaviour(self.IncomingMessageHandler())
        self.add_behaviour(self.SessionTimeoutChecker(period=self._session_timeout_seconds))
        self.add_behaviour(self.SuggestionGenerator(period=self._config.interval_suggestion_generator))
