#!/usr/bin/env python3
"""SP1 CLI entrypoint.

Usage::

    $ cd repo_root
    $ uv run python -m sp1.cli run
    $ uv run python -m sp1.cli config
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import signal
from pathlib import Path

import click
import spade

from sp1.agents.analysts.builder import AnalystBuilder
from sp1.agents.clerk.builder import ClerkBuilder
from sp1.agents.crawler.config import get_crawler_config
from sp1.agents.crawler.crawler_builder import CrawlerBuilder
from sp1.agents.editor.builder import EditorBuilder
from sp1.infra.blackboard import Blackboard
from sp1.infra.llm_config import LLMConfig
from sp1.utils.logger import get_logger

log = get_logger("sp1.cli")

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _load_dotenv(path: Path | None = None) -> None:
    """Load key-value pairs from a ``.env`` file into ``os.environ``."""
    if path is None:
        path = Path(__file__).parent.resolve() / ".env"
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _spade_server() -> str:
    return os.environ.get("SPADE_SERVER", "localhost")


def _blackboard_path() -> Path:
    return Path(os.environ.get("BLACKBOARD_PATH", "data/blackboard.json")).resolve()


# ---------------------------------------------------------------------------
# Agent orchestration
# ---------------------------------------------------------------------------


async def _spawn_all_agents(
    blackboard: Blackboard,
    spade_server: str,
    llm_config: LLMConfig,
) -> list[spade.agent.Agent]:
    """Instantiate and start every agent in the SP1 MAS.

    :return: List of started agents (for coordinated shutdown).
    """
    agents: list[spade.agent.Agent] = []

    # JIDs
    editor_jid = f"editor@{spade_server}"
    clerk_jid = f"clerk@{spade_server}"

    # ---------------------------------------------------------------
    # Editor
    # ---------------------------------------------------------------
    editor = (
        EditorBuilder()
        .with_credentials(editor_jid, "editor123")
        .with_blackboard(blackboard)
        .with_clerk_jid(clerk_jid)
        .with_llm_config(llm_config)
        .build()
    )
    await editor.start(auto_register=True)
    agents.append(editor)
    log.info("Editor %s started", editor.jid)

    # ---------------------------------------------------------------
    # Clerk
    # ---------------------------------------------------------------
    clerk = (
        ClerkBuilder()
        .with_credentials(clerk_jid, "clerk123")
        .with_blackboard(blackboard)
        .with_editor_jid(editor_jid)
        .with_user_id("default_user")
        .build()
    )
    await clerk.start(auto_register=True)
    agents.append(clerk)
    log.info("Clerk %s started", clerk.jid)

    # ---------------------------------------------------------------
    # Analysts
    # ---------------------------------------------------------------
    for dimension in ("relevance", "credibility", "novelty"):
        analyst = (
            AnalystBuilder(dimension=dimension)
            .with_credentials(f"analyst_{dimension}@{spade_server}", f"analyst_{dimension}123")
            .with_blackboard(blackboard)
            .with_editor_jid(editor_jid)
            .with_poll_interval_seconds(30)
            .build()
        )
        await analyst.start(auto_register=True)
        agents.append(analyst)
        log.info("Analyst %s started", analyst.jid)

    # ---------------------------------------------------------------
    # Crawlers (one per configured RSS feed)
    # ---------------------------------------------------------------
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
            await crawler.start(auto_register=True)
            agents.append(crawler)
            log.info("Crawler %s started for %s", crawler.jid, rss_feed.feed)

    return agents


async def _run_mas(
    blackboard: Blackboard,
    spade_server: str,
    llm_config: LLMConfig,
    persist_path: Path,
    persist_interval: int,
) -> None:
    """Main MAS loop: spawn agents, keep alive, persist blackboard, graceful shutdown."""
    agents = await _spawn_all_agents(blackboard, spade_server, llm_config)

    shutdown_event = asyncio.Event()

    def _shutdown() -> None:
        log.info("Shutdown signal received")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _shutdown)

    # Periodic persistence
    async def _persist() -> None:
        while not shutdown_event.is_set():
            await asyncio.sleep(persist_interval)
            await blackboard.save_to_json(str(persist_path))
            log.debug("Blackboard persisted to %s", persist_path)

    persist_task = asyncio.create_task(_persist())

    try:
        await shutdown_event.wait()
    finally:
        persist_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await persist_task

        # Final persist
        await blackboard.save_to_json(str(persist_path))
        log.info("Final blackboard snapshot saved to %s", persist_path)

        # Stop all agents
        for agent in agents:
            await agent.stop()
            log.info("Agent %s stopped", agent.jid)


# ---------------------------------------------------------------------------
# Click commands
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """SP1 Multi-Agent News Aggregation System CLI."""
    _load_dotenv()


@cli.command()
@click.option(
    "--blackboard-path",
    type=click.Path(path_type=Path),
    default=lambda: _blackboard_path(),
    help="Path for JSON blackboard persistence.",
)
@click.option(
    "--persist-interval",
    type=int,
    default=30,
    show_default=True,
    help="Seconds between blackboard auto-saves.",
)
@click.option(
    "--llm-model",
    type=str,
    default=None,
    help="Override OLLAMA_SUMMARIZATION_MODEL.",
)
def run(
    blackboard_path: Path,
    persist_interval: int,
    llm_model: str | None,
) -> None:
    """Start the full SP1 multi-agent system."""
    spade_server = _spade_server()
    log.info("Starting SP1 MAS on SPADE server %s", spade_server)

    # Load blackboard if snapshot exists
    blackboard = Blackboard()
    if blackboard_path.exists():
        asyncio.run(blackboard.load_from_json(str(blackboard_path)))
        log.info("Loaded blackboard snapshot from %s", blackboard_path)

    llm_config = LLMConfig()
    if llm_model:
        llm_config.summarization_model = llm_model

    try:
        asyncio.run(_run_mas(blackboard, spade_server, llm_config, blackboard_path, persist_interval))
    except KeyboardInterrupt:
        log.info("Interrupted by user")


@cli.command()
def config() -> None:
    """Display current SP1 configuration."""
    llm = LLMConfig()
    crawler_cfg = get_crawler_config()
    click.echo(
        json.dumps(
            {
                "spade_server": _spade_server(),
                "blackboard_path": str(_blackboard_path()),
                "llm": {
                    "summarization_model": llm.summarization_model,
                    "base_url": llm.base_url,
                    "temperature": llm.temperature,
                    "max_tokens": llm.max_tokens,
                    "fallback_to_extract": llm.fallback_to_extract,
                },
                "crawler": {"rss_feeds": [x.feed for x in crawler_cfg.rss_feeds]},
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    cli()
