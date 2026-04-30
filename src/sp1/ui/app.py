"""SP1 Streamlit application.

Provides a web-based interface for interacting with the multi-agent news
aggregation system:

* Chat window for querying the Clerk agent
* Blackboard inspector (candidate pool, score board, filters, etc.)
* Message log between agents
* Filter configuration panel
* Source health dashboard
* Feedback interface

Usage::

    $ cd repo_root
    $ PYTHONPATH=src uv run streamlit run src/sp1/ui/app.py

"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from sp1.ui.mas_manager import MASManager

# ---------------------------------------------------------------------------
# Environment helpers
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


# ---------------------------------------------------------------------------
# Session state initialisation (idempotent across reruns)
# ---------------------------------------------------------------------------


def _ensure_manager() -> MASManager:
    """Return the single MASManager instance for this Streamlit session."""
    session_key = "sp1_mas_manager"
    if session_key not in st.session_state:
        _load_env()
        spade_server = os.environ.get("SPADE_SERVER", "localhost")
        manager = MASManager(spade_server)
        st.session_state[session_key] = manager
    return st.session_state[session_key]


def _ensure_started(manager: MASManager) -> bool:
    if not manager.is_ready:
        with st.spinner("Initialising SP1 agents (this may take a moment)..."):
            manager.start()
    return manager.is_ready


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SP1 News Aggregation", layout="wide")
st.title("SP1 Multi-Agent News Aggregation")
st.caption("Powered by SPADE + Streamlit")

# Initialise / retrieve MAS
manager = _ensure_manager()
is_ready = _ensure_started(manager)

if is_ready:
    st.success("System ready! Connected to SPADE server.")
else:
    st.warning(
        "SPADE server appears unreachable.  "
        "Start `uv run spade run --db data/spade/server.db` and refresh the page.\n\n"
        "The blackboard will still work in local-only mode."
    )

blackboard = manager.blackboard
clerk = manager.clerk

if "chat_history" not in st.session_state:
    st.session_state.chat_history: list[dict[str, str]] = []


tabs = st.tabs(["Chat", "Filters", "Blackboard", "Messages", "Source Health"])

# ---------------------------------------------------------------
# Chat Tab
# ---------------------------------------------------------------
with tabs[0]:
    st.header("Chat with Clerk Agent")

    if clerk is None:
        st.info("Clerk agent is offline. Start the SPADE server and refresh to enable chat.")

    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("Type a command (e.g. /filter AI, technology)...")

    if user_input and clerk is not None:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        lower = user_input.strip().lower()
        response = ""

        if lower.startswith("/filter "):
            parts = user_input[8:].strip().split(",")
            keywords = [p.strip() for p in parts if p.strip()]
            try:
                fid = manager.run(clerk.register_filter(keywords=keywords, mode="one_off"))
                response = f"Registered filter **{fid}** with keywords: {', '.join(keywords)}. Requesting bundle..."
                bundle = manager.run(clerk.request_bundle(fid), timeout=15.0)
                if bundle:
                    response += f"\n\nBundle received with {len(bundle.get('articles', []))} articles:"
                    for art in bundle.get("articles", []):
                        scores = art.get("scores", {})
                        response += (
                            f"\n\n**{art.get('title', 'Untitled')}**  \n"
                            f"Source: {art.get('source_id', 'unknown')} | "
                            f"Score: {scores.get('aggregated', 'N/A')}  \n"
                            f"Summary: {art.get('summary', 'No summary')}  \n"
                            f"[Read original]({art.get('url', '#')})"
                        )
                        if art.get("conflict_flag"):
                            response += f" ⚠️ *Conflict: {art['conflict_flag']}*"
                else:
                    response += "\n\nNo matching articles found for your filter."
            except Exception as exc:
                response = f"Error: {exc}"

        elif lower == "/help":
            response = (
                "**Commands:**\n"
                "• `/filter keyword1, keyword2` — one-off search\n"
                "• `/standing keyword1, keyword2` — standing subscription\n"
                "• `/feedback article_id true/false` — rate an article\n"
                "• `/help` — show this message"
            )

        elif lower.startswith("/standing "):
            parts = user_input[10:].strip().split(",")
            keywords = [p.strip() for p in parts if p.strip()]
            try:
                fid = manager.run(
                    clerk.register_filter(
                        keywords=keywords,
                        mode="standing",
                        delivery={"max_items": 5, "min_interval_minutes": 30, "min_items_before_push": 2},
                    )
                )
                response = f"Standing filter **{fid}** registered. You'll receive automatic updates."
            except Exception as exc:
                response = f"Error: {exc}"

        elif lower.startswith("/feedback "):
            parts = user_input[10:].strip().split()
            if len(parts) >= 2:
                article_id = parts[0]
                relevant = parts[1].lower() in ("true", "yes", "1")
                try:
                    manager.run(clerk.submit_feedback(article_id, "unknown", relevant))
                    response = f"Feedback recorded for article {article_id}."
                except Exception as exc:
                    response = f"Error: {exc}"
            else:
                response = "Usage: `/feedback article_id true/false`"

        else:
            response = "I didn't understand that. Type `/help` for available commands."

        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

# ---------------------------------------------------------------
# Filters Tab
# ---------------------------------------------------------------
with tabs[1]:
    st.header("Active Filters")
    if st.button("Refresh Filters"):
        st.rerun()

    try:
        filters = manager.run(blackboard.get_all_filters())
    except Exception as exc:
        st.error(f"Error reading filters: {exc}")
        filters = []

    if not filters:
        st.info("No active filters")
    else:
        for f in filters:
            with st.expander(f"Filter: {f['filter_id']} ({f.get('mode', 'N/A')})"):
                st.write(f"**Keywords:** {', '.join(f.get('keywords', []))}")
                st.write(f"**Categories:** {', '.join(f.get('categories', []))}")
                st.write(f"**Sources:** {', '.join(f.get('sources', [])) or 'All'}")
                if st.button("Remove", key=f"remove_{f['filter_id']}") and clerk:
                    try:
                        manager.run(clerk.remove_filter(f["filter_id"]))
                        st.success(f"Filter {f['filter_id']} removed")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error: {exc}")

# ---------------------------------------------------------------
# Blackboard Tab
# ---------------------------------------------------------------
with tabs[2]:
    st.header("Blackboard Inspector")

    col1, col2, col3 = st.columns(3)
    show_pool = col1.checkbox("Candidate Pool")
    show_scores = col2.checkbox("Score Board")
    show_profiles = col3.checkbox("User Profiles")

    col4, col5 = st.columns(2)
    show_reputation = col4.checkbox("Source Reputation")
    show_pending = col5.checkbox("Pending Deliveries")

    if st.button("Refresh Blackboard"):
        st.rerun()

    if show_pool:
        try:
            articles = manager.run(blackboard.snapshot_candidate_pool())
        except Exception as exc:
            st.error(f"Error reading pool: {exc}")
            articles = []
        st.subheader(f"Candidate Pool ({len(articles)} articles)")
        if articles:
            df_data = [
                {
                    "Title": a.get("title", "Untitled")[:80],
                    "Source": a.get("source_id", ""),
                    "Published": a.get("published_at", ""),
                    "URL": a.get("url", ""),
                }
                for a in articles[:50]
            ]
            st.dataframe(df_data, width="stretch")
        else:
            st.info("No articles in candidate pool")

    if show_scores:
        try:
            scores = manager.run(blackboard.snapshot_score_board())
        except Exception as exc:
            st.error(f"Error reading scores: {exc}")
            scores = {}
        st.subheader(f"Score Board ({len(scores)} entries)")
        if scores:
            df_data = [
                {
                    "Article": k.split(":")[0][:20],
                    "Filter": k.split(":")[1] if ":" in k else "",
                    "Dimension": v.get("dimension", ""),
                    "Score": v.get("score", 0),
                }
                for k, v in list(scores.items())[:100]
            ]
            st.dataframe(df_data, width="stretch")
        else:
            st.info("No scores available")

    if show_profiles:
        try:
            profiles = manager.run(blackboard.get_all_user_profiles())
        except Exception as exc:
            st.error(f"Error reading profiles: {exc}")
            profiles = {}
        st.subheader(f"User Profiles ({len(profiles)} users)")
        for uid, prof in profiles.items():
            st.json({uid: prof})

    if show_reputation:
        try:
            rep = manager.run(blackboard.snapshot_source_reputation())
        except Exception as exc:
            st.error(f"Error reading reputation: {exc}")
            rep = {}
        st.subheader(f"Source Reputation ({len(rep)} sources)")
        if rep:
            st.bar_chart(rep)
        else:
            st.info("No reputation data")

    if show_pending:
        st.subheader("Pending Deliveries")
        st.info("Pending deliveries are queued per-user.")

# ---------------------------------------------------------------
# Messages Tab
# ---------------------------------------------------------------
with tabs[3]:
    st.header("Agent Message Log")
    st.info("Message logging is maintained by the individual agents.")

    if "message_log" in st.session_state and st.session_state.message_log:
        for entry in reversed(st.session_state.message_log[-50:]):
            with st.container():
                st.caption(f"[{entry.get('timestamp', '')}] {entry.get('sender', '')} → {entry.get('receiver', '')}")
                st.text(entry.get("body", "")[:300])
                st.divider()
    else:
        st.info("No messages logged — they appear here when agents exchange FIPA ACL messages.")

# ---------------------------------------------------------------
# Source Health Tab
# ---------------------------------------------------------------
with tabs[4]:
    st.header("Source Health Dashboard")
    if st.button("Refresh Health"):
        st.rerun()

    try:
        health = manager.run(blackboard.snapshot_source_health())
    except Exception as exc:
        st.error(f"Error reading health: {exc}")
        health = {}

    if not health:
        st.info("No source health data available")
    else:
        cols = st.columns(min(len(health), 4))
        for i, (sid, info) in enumerate(health.items()):
            status = info.get("status", "unknown")
            with cols[i % 4]:
                if status == "healthy":
                    st.success(f"**{sid}**\n\n✅ Healthy")
                else:
                    st.error(f"**{sid}**\n\n❌ {status}")
                reason = info.get("reason", "")
                if reason:
                    st.caption(f"Reason: {reason}")
