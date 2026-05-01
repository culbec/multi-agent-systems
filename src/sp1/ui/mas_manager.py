"""Background MAS orchestrator for the web UI.

Spawns the Editor, Analysts, Crawlers, and Clerk in a dedicated event-loop
thread so that page reloads do not re-create or disconnect the agents.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from typing import Any

from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from sp1.agents.analysts.builder import AnalystBuilder
from sp1.agents.clerk.builder import ClerkBuilder
from sp1.agents.clerk.clerk import ClerkAgent
from sp1.agents.crawler.config import get_crawler_config
from sp1.agents.crawler.crawler_builder import CrawlerBuilder
from sp1.agents.editor.builder import EditorBuilder
from sp1.agents.editor.editor import EditorAgent
from sp1.infra.blackboard import Blackboard
from sp1.infra.config import SP1Config
from sp1.infra.llm_config import LLMConfig
from sp1.ui.demo_data import load_demo_articles
from sp1.utils.logger import get_logger

log = get_logger("sp1.ui.mas")


class MASManager:
    """Manages the lifecycle of the SP1 MAS agents inside a background asyncio loop.

    The manager guarantees that agents are started **once** and kept alive for the
    lifetime of the Streamlit session.
    """

    _send_patched: bool = False

    def __init__(self, spade_server: str) -> None:
        self._spade_server = spade_server
        self._config = SP1Config()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._agents: list[Agent] = []
        self._blackboard = Blackboard()
        self._started = threading.Event()
        self._shutdown = threading.Event()
        self._patch_spade_send()

    @classmethod
    def _patch_spade_send(cls) -> None:
        """Monkeypatch ``CyclicBehaviour.send`` to capture outgoing messages in the blackboard log."""
        if cls._send_patched:
            return
        _original_send = CyclicBehaviour.send

        async def _patched_send(self_: CyclicBehaviour, msg: Message) -> None:
            await _original_send(self_, msg)
            try:
                agent = getattr(self_, "agent", None)
                if agent is None:
                    return
                bb = getattr(agent, "_blackboard", None)
                if bb is None:
                    return
                body_preview = (msg.body or "")[: SP1Config().message_log_body_limit]
                await bb.log_message(
                    sender=str(getattr(agent, "jid", "unknown")),
                    receiver=str(msg.to),
                    performative=msg.get_metadata("performative") or "unknown",
                    body_preview=body_preview,
                )
            except Exception:
                pass  # fail-silently: logging must never break a real send

        CyclicBehaviour.send = _patched_send  # type: ignore[method-assign]
        cls._send_patched = True

    # ------------------------------------------------------------------
    # Async bootstrap (runs inside the background loop)
    # ------------------------------------------------------------------

    async def _start_all(self) -> None:
        """Start Editor, Analysts, and Clerk sequentially with short timeouts."""
        spade_server = self._spade_server
        blackboard = self._blackboard
        llm_config = LLMConfig()
        cfg = self._config

        # Pre-populate with demo articles so users get instant results
        await load_demo_articles(blackboard)
        log.info("Blackboard candidate pool: %d articles", len(await blackboard.snapshot_candidate_pool()))

        editor_jid = f"editor@{spade_server}"
        clerk_jid = f"clerk_ui@{spade_server}"

        # Editor -------------------------------------------------------
        editor: EditorAgent = (
            EditorBuilder()
            .with_credentials(editor_jid, cfg.password_editor)
            .with_blackboard(blackboard)
            .with_clerk_jid(clerk_jid)
            .with_llm_config(llm_config)
            .build()
        )
        try:
            await asyncio.wait_for(editor.start(auto_register=True), timeout=cfg.timeout_agent_startup)
            self._agents.append(editor)
            log.info("Editor %s started", editor.jid)
        except asyncio.TimeoutError:
            log.warning("Editor connection timed out — some features will be limited")
            await editor.stop()

        # Analysts (run even without Editor for blackboard scoring) ----
        for dimension in ("relevance", "credibility", "novelty"):
            analyst = (
                AnalystBuilder(dimension=dimension)
                .with_credentials(
                    f"analyst_{dimension}@{spade_server}",
                    f"{cfg.password_analyst_prefix}{dimension}123",
                )
                .with_blackboard(blackboard)
                .with_editor_jid(editor_jid)
                .with_poll_interval_seconds(cfg.interval_analyst_poll)
                .build()
            )
            try:
                await asyncio.wait_for(analyst.start(auto_register=True), timeout=cfg.timeout_agent_startup)
                self._agents.append(analyst)
                log.info("Analyst %s started", analyst.jid)
            except asyncio.TimeoutError:
                log.warning("Analyst %s connection timed out", analyst.jid)
                await analyst.stop()

        # Crawlers (one per configured RSS feed) ----------------------
        try:
            crawler_config = get_crawler_config()
        except ValueError as exc:
            log.warning("Could not load crawler config: %s", exc)
            crawler_config = None

        if crawler_config:
            for rss_feed in crawler_config.rss_feeds:
                source_id = hashlib.md5(rss_feed.feed.encode(), usedforsecurity=False).hexdigest()
                crawler = (
                    CrawlerBuilder()
                    .with_credentials(
                        jid=f"crawler_{rss_feed.name}@{spade_server}",
                        password=rss_feed.password,
                    )
                    .with_source(source_id=source_id, rss_url=rss_feed.feed)
                    .with_blackboard(blackboard)
                    .with_editor_jid(editor_jid)
                    .with_poll_interval_seconds(rss_feed.poll_interval_seconds)
                    .build()
                )
                try:
                    await asyncio.wait_for(crawler.start(auto_register=True), timeout=cfg.timeout_agent_startup)
                    self._agents.append(crawler)
                    log.info("Crawler %s started for %s", crawler.jid, rss_feed.feed)
                except asyncio.TimeoutError:
                    log.warning("Crawler %s connection timed out for %s", crawler.jid, rss_feed.feed)
                    await crawler.stop()

        # Clerk (UI-facing) -------------------------------------------
        clerk: ClerkAgent = (
            ClerkBuilder()
            .with_credentials(clerk_jid, cfg.password_clerk)
            .with_blackboard(blackboard)
            .with_editor_jid(editor_jid)
            .with_user_id("ui_user")
            .build()
        )
        try:
            await asyncio.wait_for(clerk.start(auto_register=True), timeout=cfg.timeout_agent_startup)
            self._agents.append(clerk)
            log.info("Clerk %s started", clerk.jid)
        except asyncio.TimeoutError:
            log.warning("Clerk connection timed out — UI chat unavailable")
            await clerk.stop()

        self._started.set()

    async def _stop_all(self) -> None:
        """Gracefully stop all agents."""
        for agent in reversed(self._agents):
            try:
                await agent.stop()
                log.info("Agent %s stopped", agent.jid)
            except Exception as exc:
                log.debug("Error stopping %s: %s", agent.jid, exc)
        self._agents.clear()

    async def _main_loop(self) -> None:
        """Single coroutine that starts agents, keeps the loop alive, then shuts down."""
        try:
            await self._start_all()
            while not self._shutdown.is_set():
                await asyncio.sleep(1)
        finally:
            await self._stop_all()

    # ------------------------------------------------------------------
    # Public API (callable from the Streamlit main thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background event loop and bootstrap all agents."""
        if self._thread is not None and self._thread.is_alive():
            log.debug("MAS background thread already running")
            return

        # Reset lifecycle flags for idempotent restart
        self._shutdown.clear()
        self._started.clear()
        self._agents.clear()
        self._thread = None
        self._loop = asyncio.new_event_loop()

        def _run() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._main_loop())

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

        # Block until agents are started (or timeout)
        started = self._started.wait(timeout=self._config.timeout_mas_startup)
        if not started:
            log.warning("MAS startup did not complete within 30 seconds")

    def stop(self) -> None:
        """Signal the background loop to stop and wait for agents to terminate."""
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=self._config.timeout_thread_join)

    def run(self, coro: Any, timeout: float | None = None) -> Any:
        """Run *coro* on the background loop and return its result."""
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("MAS background loop is not running")
        if timeout is None:
            timeout = self._config.timeout_run_coro
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    async def arun(self, coro: Any, timeout: float | None = None) -> Any:
        """Run *coro* on the background loop from an async context.

        Uses ``run_in_executor`` so the calling async function is not blocked.
        """
        if timeout is None:
            timeout = self._config.timeout_run_coro
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, coro, timeout)

    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def blackboard(self) -> Blackboard:
        return self._blackboard

    @property
    def clerk(self) -> ClerkAgent | None:
        for a in self._agents:
            if isinstance(a, ClerkAgent):
                return a
        return None

    @property
    def editor(self) -> EditorAgent | None:
        for a in self._agents:
            if isinstance(a, EditorAgent):
                return a
        return None

    @property
    def is_ready(self) -> bool:
        return self._started.is_set() and any(isinstance(a, ClerkAgent) for a in self._agents)
