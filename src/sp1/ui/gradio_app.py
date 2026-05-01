"""SP1 Gradio UI.

A proper web application for the multi-agent news aggregation system.
Unlike Streamlit, Gradio runs a persistent server that does NOT re-execute
on every interaction, making it compatible with long-lived SPADE agents.

Usage::

    $ cd repo_root
    $ PYTHONPATH=src uv run python -m sp1.ui.gradio_app

"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import gradio as gr

from sp1.infra.config import SP1Config
from sp1.infra.llm_config import LLMConfig
from sp1.ui.mas_manager import MASManager
from sp1.utils.logger import get_logger

log = get_logger("sp1.ui.gradio")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

cfg = SP1Config()

SP1_LATEST_THRESHOLD = cfg.latest_threshold
SP1_CLERK_LLM_ENABLED = cfg.clerk_llm_enabled
SP1_CLERK_MAX_ARTICLES = cfg.clerk_max_articles


# ---------------------------------------------------------------------------
# Bootstrap (once per process)
# ---------------------------------------------------------------------------


def _load_env(path: Path | None = None) -> None:
    if path is None:
        path = Path(__file__).parent.parent / ".env"
    if not path.is_file():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()
_spade_server = os.environ.get("SPADE_SERVER", "localhost")

# Start the MAS in the background
manager = MASManager(_spade_server)


def ensure_started() -> str:
    if manager.is_ready:
        n = len(manager.run(manager.blackboard.snapshot_candidate_pool()))
        return f"Connected — {n} articles in pool"
    manager.start()
    if manager.is_ready:
        n = len(manager.run(manager.blackboard.snapshot_candidate_pool()))
        return f"Connected — {n} articles in pool"
    return "SPADE server unreachable — running in local mode"


# ---------------------------------------------------------------------------
# Helpers — Articles / Formatting
# ---------------------------------------------------------------------------


def get_latest_articles(limit: int = SP1_LATEST_THRESHOLD) -> list[dict[str, Any]]:
    """Return candidate pool sorted by published date desc, capped at *limit*."""
    try:
        articles = manager.run(manager.blackboard.snapshot_candidate_pool())
    except Exception:
        return []

    def _published_at(a: dict[str, Any]) -> str:
        return a.get("published_at") or "1970-01-01T00:00:00+00:00"

    sorted_articles = sorted(
        articles,
        key=_published_at,
        reverse=True,
    )
    return sorted_articles[:limit]


async def _llm_format_articles(
    articles: list[dict[str, Any]],
    user_query: str = "",
    preamble: str = "",
) -> str:
    """Ask Ollama to produce a nicely formatted, conversational article digest."""
    if not articles:
        return "I couldn't find any articles matching your request. Try broadening your keywords or checking the News Feed."
    if not SP1_CLERK_LLM_ENABLED:
        return _format_bundle_simple(articles, preamble=preamble)

    llm = LLMConfig()

    # Build compact article stubs
    lines: list[str] = []
    for i, a in enumerate(articles[:SP1_CLERK_MAX_ARTICLES], 1):
        title = (a.get("title") or "Untitled").replace("\n", " ")
        summary = (a.get("summary") or a.get("body", "")[:120]).replace("\n", " ")
        src = a.get("source_id", "unknown")
        scores = a.get("scores", {})

        def _fmt(key: str) -> str:
            v = scores.get(key)
            return f"{v:.2f}" if isinstance(v, (int, float)) else "?"

        sc = f"rel={_fmt('relevance')} cred={_fmt('credibility')} nov={_fmt('novelty')}"
        lines.append(f"{i}. [{src}] {title} ({sc})\n   {summary}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    preamble_text = f"{preamble} Here are the results (as of {now}):"

    prompt = (
        "You are a helpful news assistant called the Clerk. You are friendly, concise, and natural.\n"
        "Start with a brief greeting or context. Present the articles as a clean digest.\n"
        "At the end, suggest 1-2 follow-up actions the user might take.\n\n"
        f"Context: {user_query or 'latest news'}\n"
        f"{preamble_text}\n\n" + "\n".join(lines) + "\n\nClerk:"
    )

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=llm.timeout_seconds)) as session:
            payload = {
                "model": llm.summarization_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": llm.temperature,
                    "num_predict": llm.max_tokens,
                },
            }
            async with session.post(f"{llm.base_url}/api/generate", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    text = data.get("response", "").strip()
                    if text:
                        return text
    except Exception as exc:
        log.warning("LLM clerk formatting failed: %s", exc)

    return _format_bundle_simple(articles, preamble=preamble)


def _format_bundle_simple(articles: list[dict[str, Any]], preamble: str = "") -> str:
    """Fallback plain-text formatting (no LLM) — still wraps with preamble and tips."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    if preamble:
        lines.append(f"**{preamble}**\n")
    lines.append(f"_Showing {len(articles)} article(s) as of {now}:_\n")

    for i, art in enumerate(articles, 1):
        scores = art.get("scores", {})
        conflict = art.get("conflict_flag")
        lines.append(
            f"\n**{i}.** [{art.get('source_id', 'unknown')}] **{art.get('title', 'Untitled')}**\n"
            f"   Relevance: {scores.get('relevance', 'N/A')} | "
            f"Credibility: {scores.get('credibility', 'N/A')} | "
            f"Novelty: {scores.get('novelty', 'N/A')}\n"
            f"   {art.get('summary', 'No summary')}\n"
            f"   🔗 {art.get('url', '#')}"
        )
        if conflict:
            lines.append(f"   ⚠️ Conflict: {conflict}")

    # Follow-up suggestions
    lines.append(
        "\n---\n"
        "**💡 Tips:** Try `/filter keyword1, keyword2` for a targeted search, "
        "or `/standing keyword` to get automatic updates."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Chat handler
# ---------------------------------------------------------------------------


async def chat_handler(message: str) -> str:
    """Process a user command and return a response string."""
    clerk = manager.clerk
    if clerk is None:
        return "Clerk agent is offline. Start the SPADE server and restart the UI."

    # Re-activate session on every user interaction
    if not clerk._session_active:
        clerk.activate_session()

    lower = message.strip().lower()

    if lower.startswith("/filter "):
        parts = message[8:].strip().split(",")
        keywords = [p.strip() for p in parts if p.strip()]
        try:
            fid = await manager.arun(clerk.register_filter(keywords=keywords, mode="one_off"))
            bundle = await manager.arun(clerk.request_bundle(fid), timeout=cfg.timeout_bundle_request)
            if bundle:
                articles = bundle.get("articles", [])
                return await _llm_format_articles(articles, user_query=f"/filter {', '.join(keywords)}")
            return f"Registered filter {fid} with keywords: {', '.join(keywords)}.\n\nNo matching articles found."
        except Exception as exc:
            return f"Error: {exc}"

    elif lower == "/help":
        return (
            "👋 **Welcome!** I am the SP1 Clerk — your news assistant.\n\n"
            "**Commands:**\n"
            "• `/filter keyword1, keyword2` — one-off search (latest 10)\n"
            "• `/standing keyword1, keyword2` — standing subscription (auto-delivery)\n"
            "• `/feedback article_id true/false` — rate an article\n"
            "• `/articles` — view latest articles from the pool\n"
            "• `/help` — show this message\n\n"
            'You can also ask me anything naturally, like "What\'s new in climate?".'
        )

    elif lower.startswith("/standing "):
        parts = message[10:].strip().split(",")
        keywords = [p.strip() for p in parts if p.strip()]
        try:
            fid = await manager.arun(
                clerk.register_filter(
                    keywords=keywords,
                    mode="standing",
                    delivery={
                        "max_items": 5,
                        "min_interval_minutes": cfg.limit_min_interval_minutes,
                        "min_items_before_push": cfg.limit_min_items_before_push,
                    },
                )
            )
            return (
                f"📬 **Standing filter `{fid}`** registered!\n\n"
                f"Keywords: _{', '.join(keywords)}_\n\n"
                "You will receive automatic updates in this chat and in the News Feed "
                "whenever matching articles arrive."
            )
        except Exception as exc:
            return f"❌ Error: {exc}"

    elif lower.startswith("/feedback "):
        parts = message[10:].strip().split()
        if len(parts) >= 2:
            article_id = parts[0]
            relevant = parts[1].lower() in ("true", "yes", "1")
            try:
                await manager.arun(clerk.submit_feedback(article_id, "unknown", relevant))
                em = "👍" if relevant else "👎"
                return f"{em} **Feedback noted** for article `{article_id}`: relevant={relevant}. Thanks!"
            except Exception as exc:
                return f"❌ Error: {exc}"
        return "ℹ️ Usage: `/feedback article_id true/false`"

    elif lower == "/articles":
        articles = get_latest_articles(SP1_LATEST_THRESHOLD)
        if not articles:
            return "📭 The candidate pool is empty right now. Check back later or register a standing filter to be notified when new articles arrive."
        return await _llm_format_articles(
            articles,
            user_query="/articles (latest)",
            preamble="Here are the latest articles in the pool:",
        )

    else:
        # Treat as a natural-language query
        articles = get_latest_articles(SP1_LATEST_THRESHOLD)
        return await _llm_format_articles(
            articles,
            user_query=message.strip(),
            preamble=f'You asked: "{message.strip()}"',
        )


# ---------------------------------------------------------------------------
# Data refreshers (for Gradio components)
# ---------------------------------------------------------------------------


def get_articles() -> str:
    articles = get_latest_articles(SP1_LATEST_THRESHOLD)
    if not articles:
        return "No articles in the pool."
    lines = [f"Latest Articles ({len(articles)} shown, sorted by date)"]
    lines.append("")
    for i, art in enumerate(articles[:SP1_LATEST_THRESHOLD], 1):
        body_preview = art.get("summary") or art.get("body", "")[: cfg.limit_body_preview_chars]
        pub = art.get("published_at", "unknown")[:16]
        lines.append(f"  {i}. {art.get('title', 'Untitled')}")
        lines.append(f"      Source: {art.get('source_id', '--')}  |  Published: {pub}")
        lines.append(f"      {body_preview[: cfg.limit_body_preview_chars]}...")
        lines.append(f"      URL: {art.get('url', '#')}")
        lines.append("")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_filters() -> str:
    try:
        filters = manager.run(manager.blackboard.get_all_filters())
    except Exception as exc:
        return f"Error: {exc}"
    if not filters:
        return "No active filters."
    lines = ["Active Filters"]
    lines.append("")
    for f in filters:
        lines.append(f"  ID:       {f['filter_id']}")
        lines.append(f"  Mode:     {f.get('mode', 'N/A')}")
        lines.append(f"  Keywords: {', '.join(f.get('keywords', []))}")
        lines.append(f"  Categories: {', '.join(f.get('categories', [])) or '--'}")
        lines.append("")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_scores() -> str:
    try:
        scores = manager.run(manager.blackboard.snapshot_score_board())
    except Exception as exc:
        return f"Error: {exc}"
    if not scores:
        return "No scores computed yet."
    lines = [f"Score Board — {len(scores)} entries"]
    for key, vec in list(scores.items())[: cfg.limit_score_board_display]:
        dim = vec.get("dimension", "?")
        sc = vec.get("score", 0)
        lines.append(f"{key:<50}  {dim:<12}  {sc:.3f}")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_health() -> str:
    try:
        health = manager.run(manager.blackboard.snapshot_source_health())
    except Exception as exc:
        return f"Error: {exc}"
    if not health:
        return "No source health data."
    lines = ["Source Health"]  # plain header, table rendered inside fence
    for sid, info in health.items():
        status = info.get("status", "unknown")
        emoji = "OK" if status == "healthy" else "FAIL"
        reason = info.get("reason", "")
        line = f"  {emoji:<4}  {sid:<30}  {status:<12}"
        if reason:
            line += f"  ({reason})"
        lines.append(line)
    return "```text\n" + "\n".join(lines) + "\n```"


def get_config() -> str:
    llm = LLMConfig()
    payload = {
        "spade_server": _spade_server,
        "latest_threshold": SP1_LATEST_THRESHOLD,
        "clerk_llm_enabled": SP1_CLERK_LLM_ENABLED,
        "clerk_max_articles": SP1_CLERK_MAX_ARTICLES,
        "llm": {
            "summarization_model": llm.summarization_model,
            "base_url": llm.base_url,
            "temperature": llm.temperature,
            "max_tokens": llm.max_tokens,
        },
        "status": ensure_started(),
    }
    return "```json\n" + json.dumps(payload, indent=2) + "\n```"


def get_status() -> str:
    return ensure_started()


# ---------------------------------------------------------------------------
# New: BundleQuery helpers
# ---------------------------------------------------------------------------


def get_bundles() -> str:
    try:
        bundles = manager.run(manager.blackboard.snapshot_bundle_registry())
    except Exception as exc:
        return f"Error: {exc}"
    if not bundles:
        return "No bundles recorded yet."
    lines = ["Recorded Bundles"]
    lines.append("")
    for b in bundles:
        lines.append(
            f"  {b['bundle_id']:<40}  filter={b.get('filter_id', 'N/A'):<20}  "
            f"articles={len(b.get('articles', []))}  trigger={b.get('trigger', 'N/A')}"
        )
    return "```text\n" + "\n".join(lines) + "\n```"


def get_bundle_detail(bundle_id: str) -> str:
    if not bundle_id or not bundle_id.strip():
        return "Enter a bundle ID above and click Lookup."
    bundle_id = bundle_id.strip()
    try:
        bundle = manager.run(manager.blackboard.get_bundle(bundle_id))
    except Exception as exc:
        return f"Error: {exc}"
    if bundle is None:
        return f"Bundle `{bundle_id}` not found."
    lines = [f"Bundle: {bundle_id}  (Filter: {bundle.get('filter_id', 'N/A')})"]
    lines.append(f"Trigger: {bundle.get('trigger', 'N/A')}  |  Composed: {bundle.get('composed_at', 'N/A')}")
    lines.append("")
    for i, art in enumerate(bundle.get("articles", []), 1):
        scores = art.get("scores", {})
        lines.append(f"  {i}. {art.get('title', 'Untitled')}")
        lines.append(f"      Source: {art.get('source_id', '--')}  |  Scores: rel={scores.get('relevance', '?')} cred={scores.get('credibility', '?')} nov={scores.get('novelty', '?')}")
        lines.append(f"      {art.get('summary', 'No summary')[:200]}")
        lines.append(f"      🔗 {art.get('url', '#')}")
        lines.append("")
    return "```text\n" + "\n".join(lines) + "\n```"


# ---------------------------------------------------------------------------
# New: Message Log helper
# ---------------------------------------------------------------------------


def get_message_log(limit: int = 200) -> str:
    try:
        logs = manager.run(manager.blackboard.snapshot_message_log(limit))
    except Exception as exc:
        return f"Error: {exc}"
    if not logs:
        return "No messages logged yet."
    lines = [f"{'Time':<20} {'Sender':<30} {'Receiver':<30} {'Perf':<10} Body Preview"]
    lines.append("-" * 120)
    for entry in logs:
        ts = entry.get("timestamp", "")[:19]
        sender = entry.get("sender", "")[:28]
        receiver = entry.get("receiver", "")[:28]
        perf = entry.get("performative", "")[:8]
        body = entry.get("body_preview", "")[:80]
        lines.append(f"{ts:<20} {sender:<30} {receiver:<30} {perf:<10} {body}")
    return "```text\n" + "\n".join(lines) + "\n```"


# ---------------------------------------------------------------------------
# New: Debug section helpers (full blackboard visibility)
# ---------------------------------------------------------------------------


def get_source_reputation() -> str:
    try:
        rep = manager.run(manager.blackboard.snapshot_source_reputation())
    except Exception as exc:
        return f"Error: {exc}"
    if not rep:
        return "No source reputation data."
    lines = ["Source Reputation"]
    lines.append("")
    for sid, score in rep.items():
        lines.append(f"  {sid:<30}  {score:.3f}")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_user_profiles() -> str:
    try:
        profiles = manager.run(manager.blackboard.get_all_user_profiles())
    except Exception as exc:
        return f"Error: {exc}"
    if not profiles:
        return "No user profiles."
    lines = ["User Profiles"]
    lines.append("")
    for uid, prof in profiles.items():
        lines.append(f"  {uid}: {json.dumps(prof, default=str)[:200]}")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_pending_deliveries() -> str:
    try:
        # pending_delivery_queue is keyed by user_id -> list of bundles
        queue = manager.run(manager.blackboard.snapshot_pending_deliveries())
    except Exception as exc:
        return f"Error: {exc}"
    if not queue:
        return "No pending deliveries."
    lines = ["Pending Deliveries"]
    lines.append("")
    for user_id, bundles in queue.items():
        lines.append(f"  User: {user_id} — {len(bundles)} bundle(s)")
        for b in bundles:
            lines.append(f"    - {b.get('bundle_id', '?'):<40}  articles={len(b.get('articles', []))}")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_delivery_history() -> str:
    try:
        # Use the blackboard's delivery_history directly
        # Need to access it — iterate over known users or expose a snapshot method.
        # For now, query for the clerk's user_id as a proxy.
        clerk = manager.clerk
        user_id = clerk._user_id if clerk else "ui_user"
        history = manager.run(manager.blackboard.get_delivery_history(user_id))
    except Exception as exc:
        return f"Error: {exc}"
    if not history:
        return "No delivery history."
    lines = [f"Delivery History for {user_id}"]
    lines.append("")
    for entry in history[-50:]:
        lines.append(f"  {entry.get('article_id', '?'):<30}  bundle={entry.get('bundle_id', '?')}")
    return "```text\n" + "\n".join(lines) + "\n```"


def get_feedback_history() -> str:
    try:
        clerk = manager.clerk
        user_id = clerk._user_id if clerk else "ui_user"
        history = manager.run(manager.blackboard.get_feedback_history(user_id))
    except Exception as exc:
        return f"Error: {exc}"
    if not history:
        return "No feedback history."
    lines = [f"Feedback History for {user_id}"]
    lines.append("")
    for entry in history[-50:]:
        rel = "👍" if entry.get("relevant") else "👎"
        lines.append(
            f"  {rel}  article={entry.get('article_id', '?'):<30}  "
            f"filter={entry.get('filter_id', '?'):<20}  notes={entry.get('notes', '')[:40]}"
        )
    return "```text\n" + "\n".join(lines) + "\n```"


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


with gr.Blocks(title="SP1 News Aggregation") as demo:
    gr.Markdown("# SP1 Multi-Agent News Aggregation")
    gr.Markdown("Powered by SPADE + Gradio + Ollama")

    status_text = gr.Markdown(get_status())

    with gr.Tabs():
        # -------------------------------------------------------------
        # Chat Tab
        # -------------------------------------------------------------
        with gr.Tab("Chat"):
            chatbot = gr.Chatbot(label="Clerk Agent (LLM-enhanced)")
            chat_state = gr.State(value=[])
            msg_input = gr.Textbox(
                label="Command or query",
                placeholder="Type /filter AI or ask a natural question...",
                lines=1,
            )
            send_btn = gr.Button("Send", variant="primary")
            clear_btn = gr.Button("Clear")
            bundle_status = gr.Markdown("")

            async def _respond(message: str, history: list[Any]) -> tuple[list[Any], list[Any], str]:
                if not message.strip():
                    return history or [], history or [], ""
                history = history or []
                response = await chat_handler(message)
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": response})
                return history, history, ""

            send_btn.click(
                _respond,
                inputs=[msg_input, chat_state],
                outputs=[chatbot, chat_state, msg_input],
            )
            msg_input.submit(
                _respond,
                inputs=[msg_input, chat_state],
                outputs=[chatbot, chat_state, msg_input],
            )

            # Auto-deliver standing-filter bundles into the chat
            def _check_bundles(history: list[Any]) -> tuple[list[Any], list[Any], str]:
                if manager.clerk is None:
                    return history or [], history or [], ""
                try:
                    bundle = manager.run(
                        manager.clerk.get_next_bundle(timeout=cfg.timeout_get_next_bundle),
                        timeout=2.0,
                    )
                except Exception:
                    return history or [], history or [], ""
                if bundle is None:
                    return history or [], history or [], ""
                history = history or []
                articles = bundle.get("articles", [])
                text = _format_bundle_simple(
                    articles,
                    preamble=f"🕐 New standing-filter delivery — {bundle.get('bundle_id', '')[:8]}",
                )
                history.append({"role": "assistant", "content": text})
                return history, history, ""

            bundle_timer = gr.Timer(value=cfg.timer_bundles_refresh, active=True)
            bundle_timer.tick(
                _check_bundles,
                inputs=[chat_state],
                outputs=[chatbot, chat_state, bundle_status],
            )

            clear_btn.click(lambda: ([], [], ""), outputs=[chatbot, chat_state, msg_input])

        # -------------------------------------------------------------
        # News Feed Tab
        # -------------------------------------------------------------
        with gr.Tab("News Feed"):
            feed_md = gr.Markdown(get_articles())
            refresh_feed = gr.Button("Refresh")
            refresh_feed.click(get_articles, outputs=feed_md)
            feed_timer = gr.Timer(value=cfg.timer_news_feed_refresh)
            feed_timer.tick(get_articles, outputs=feed_md)

        # -------------------------------------------------------------
        # Filters Tab
        # -------------------------------------------------------------
        with gr.Tab("Filters"):
            filters_md = gr.Markdown(get_filters())
            refresh_filters = gr.Button("Refresh")
            refresh_filters.click(get_filters, outputs=filters_md)
            filters_timer = gr.Timer(value=cfg.timer_filters_refresh)
            filters_timer.tick(get_filters, outputs=filters_md)

        # -------------------------------------------------------------
        # Bundles Tab (NEW)
        # -------------------------------------------------------------
        with gr.Tab("Bundles"):
            bundles_md = gr.Markdown(get_bundles())
            refresh_bundles = gr.Button("Refresh Bundle List")
            refresh_bundles.click(get_bundles, outputs=bundles_md)
            bundles_timer = gr.Timer(value=cfg.timer_bundles_refresh)
            bundles_timer.tick(get_bundles, outputs=bundles_md)

            gr.Markdown("---")
            gr.Markdown("### Lookup Bundle by ID")
            bundle_id_input = gr.Textbox(label="Bundle ID", placeholder="paste bundle_id here")
            lookup_btn = gr.Button("Lookup")
            bundle_detail_md = gr.Markdown("Enter a bundle ID above and click Lookup.")
            lookup_btn.click(get_bundle_detail, inputs=bundle_id_input, outputs=bundle_detail_md)

        # -------------------------------------------------------------
        # Debug Tab Group (NEW)
        # -------------------------------------------------------------
        with gr.Tab("Debug"):
            with gr.Tabs():
                with gr.Tab("Score Board"):
                    scores_md = gr.Markdown(get_scores())
                    refresh_scores = gr.Button("Refresh Scores")
                    refresh_scores.click(get_scores, outputs=scores_md)
                    scores_timer = gr.Timer(value=cfg.timer_scores_refresh)
                    scores_timer.tick(get_scores, outputs=scores_md)

                with gr.Tab("Source Health"):
                    health_md = gr.Markdown(get_health())
                    refresh_health = gr.Button("Refresh")
                    refresh_health.click(get_health, outputs=health_md)
                    health_timer = gr.Timer(value=cfg.timer_source_health_refresh)
                    health_timer.tick(get_health, outputs=health_md)

                with gr.Tab("Source Reputation"):
                    rep_md = gr.Markdown(get_source_reputation())
                    refresh_rep = gr.Button("Refresh")
                    refresh_rep.click(get_source_reputation, outputs=rep_md)
                    rep_timer = gr.Timer(value=cfg.timer_debug_refresh)
                    rep_timer.tick(get_source_reputation, outputs=rep_md)

                with gr.Tab("User Profiles"):
                    prof_md = gr.Markdown(get_user_profiles())
                    refresh_prof = gr.Button("Refresh")
                    refresh_prof.click(get_user_profiles, outputs=prof_md)
                    prof_timer = gr.Timer(value=cfg.timer_debug_refresh)
                    prof_timer.tick(get_user_profiles, outputs=prof_md)

                with gr.Tab("Pending Deliveries"):
                    pending_md = gr.Markdown(get_pending_deliveries())
                    refresh_pending = gr.Button("Refresh")
                    refresh_pending.click(get_pending_deliveries, outputs=pending_md)
                    pending_timer = gr.Timer(value=cfg.timer_debug_refresh)
                    pending_timer.tick(get_pending_deliveries, outputs=pending_md)

                with gr.Tab("Delivery History"):
                    deliv_md = gr.Markdown(get_delivery_history())
                    refresh_deliv = gr.Button("Refresh")
                    refresh_deliv.click(get_delivery_history, outputs=deliv_md)
                    deliv_timer = gr.Timer(value=cfg.timer_debug_refresh)
                    deliv_timer.tick(get_delivery_history, outputs=deliv_md)

                with gr.Tab("Feedback History"):
                    fb_md = gr.Markdown(get_feedback_history())
                    refresh_fb = gr.Button("Refresh")
                    refresh_fb.click(get_feedback_history, outputs=fb_md)
                    fb_timer = gr.Timer(value=cfg.timer_debug_refresh)
                    fb_timer.tick(get_feedback_history, outputs=fb_md)

                with gr.Tab("Message Log"):
                    log_md = gr.Markdown(get_message_log())
                    refresh_log = gr.Button("Refresh")
                    refresh_log.click(get_message_log, outputs=log_md)
                    log_timer = gr.Timer(value=cfg.timer_message_log_refresh)
                    log_timer.tick(get_message_log, outputs=log_md)

                with gr.Tab("Config"):
                    config_md = gr.Markdown(get_config())
                    refresh_config = gr.Button("Refresh")
                    refresh_config.click(get_config, outputs=config_md)
                    config_timer = gr.Timer(value=cfg.timer_config_refresh)
                    config_timer.tick(get_config, outputs=config_md)

    # Global auto-refresh for the status text
    status_timer = gr.Timer(value=cfg.timer_status_refresh)
    status_timer.tick(get_status, outputs=status_text)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
