from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SP1Config(BaseModel):
    """Centralised, environment-variable-driven configuration for SP1.

    All user-facing tunables are exposed as environment variables with the
    ``SP1_`` prefix.  Internal heuristic weights and constants that are not
    expected to change per-deployment remain hardcoded in the agent code.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # UI / Gradio
    # ------------------------------------------------------------------
    latest_threshold: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LATEST_THRESHOLD", "10"))
    )
    clerk_llm_enabled: bool = Field(
        default_factory=lambda: os.environ.get("SP1_CLERK_LLM_ENABLED", "true").lower() == "true"
    )
    clerk_max_articles: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_CLERK_MAX_ARTICLES", "10"))
    )

    # ------------------------------------------------------------------
    # Message log & Bundle registry
    # ------------------------------------------------------------------
    message_log_maxlen: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_MESSAGE_LOG_MAXLEN", "1000"))
    )
    message_log_body_limit: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_MESSAGE_LOG_BODY_LIMIT", "500"))
    )
    bundle_registry_maxlen: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_BUNDLE_REGISTRY_MAXLEN", "500"))
    )

    # ------------------------------------------------------------------
    # Timeouts (seconds)
    # ------------------------------------------------------------------
    timeout_bundle_request: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_BUNDLE_REQUEST", "30.0"))
    )
    timeout_agent_startup: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_AGENT_STARTUP", "5.0"))
    )
    timeout_mas_startup: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_MAS_STARTUP", "30.0"))
    )
    timeout_thread_join: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_THREAD_JOIN", "10.0"))
    )
    timeout_run_coro: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_RUN_CORO", "10.0"))
    )
    timeout_get_next_bundle: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMEOUT_GET_NEXT_BUNDLE", "0.5"))
    )

    # ------------------------------------------------------------------
    # Intervals (seconds)
    # ------------------------------------------------------------------
    interval_crawler_poll: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_INTERVAL_CRAWLER_POLL", "600"))
    )
    interval_analyst_poll: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_INTERVAL_ANALYST_POLL", "30"))
    )
    interval_standing_watch: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_INTERVAL_STANDING_WATCH", "30"))
    )
    interval_suggestion_generator: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_INTERVAL_SUGGESTION", "300"))
    )
    interval_session_timeout: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_INTERVAL_SESSION_TIMEOUT", "300"))
    )

    # ------------------------------------------------------------------
    # Scoring thresholds
    # ------------------------------------------------------------------
    score_breaking_threshold: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_SCORE_BREAKING_THRESHOLD", "0.95"))
    )
    score_high_score: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_SCORE_HIGH_SCORE", "0.6"))
    )
    score_min_credibility: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_SCORE_MIN_CREDIBILITY", "0.15"))
    )

    # ------------------------------------------------------------------
    # Limits
    # ------------------------------------------------------------------
    limit_pool_size: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_POOL_SIZE", "5000"))
    )
    limit_max_articles_per_crawl: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_MAX_ARTICLES_PER_CRAWL", "50"))
    )
    limit_bundle_max_items: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_BUNDLE_MAX_ITEMS", "10"))
    )
    limit_standing_push_ids: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_STANDING_PUSH_IDS", "500"))
    )
    limit_min_items_before_push: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_MIN_ITEMS_BEFORE_PUSH", "3"))
    )
    limit_min_interval_minutes: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_MIN_INTERVAL_MINUTES", "60"))
    )
    limit_body_preview_chars: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_BODY_PREVIEW_CHARS", "180"))
    )
    limit_score_board_display: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_LIMIT_SCORE_BOARD_DISPLAY", "100"))
    )

    # ------------------------------------------------------------------
    # Suggestion heuristics
    # ------------------------------------------------------------------
    suggestion_delivery_threshold: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_SUGGESTION_DELIVERY_THRESHOLD", "20"))
    )
    suggestion_feedback_threshold: int = Field(
        default_factory=lambda: int(os.environ.get("SP1_SUGGESTION_FEEDBACK_THRESHOLD", "5"))
    )

    # ------------------------------------------------------------------
    # Security / Agent passwords
    # ------------------------------------------------------------------
    password_editor: str = Field(
        default_factory=lambda: os.environ.get("SP1_PASSWORD_EDITOR", "editor123")
    )
    password_clerk: str = Field(
        default_factory=lambda: os.environ.get("SP1_PASSWORD_CLERK", "clerk123")
    )
    password_analyst_prefix: str = Field(
        default_factory=lambda: os.environ.get("SP1_PASSWORD_ANALYST_PREFIX", "analyst_")
    )

    # ------------------------------------------------------------------
    # Gradio refresh timers (seconds)
    # ------------------------------------------------------------------
    timer_message_log_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_MESSAGE_LOG_REFRESH", "5"))
    )
    timer_bundles_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_BUNDLES_REFRESH", "15"))
    )
    timer_news_feed_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_NEWS_FEED_REFRESH", "10"))
    )
    timer_filters_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_FILTERS_REFRESH", "10"))
    )
    timer_scores_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_SCORES_REFRESH", "10"))
    )
    timer_source_health_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_SOURCE_HEALTH_REFRESH", "30"))
    )
    timer_config_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_CONFIG_REFRESH", "60"))
    )
    timer_status_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_STATUS_REFRESH", "15"))
    )
    timer_debug_refresh: float = Field(
        default_factory=lambda: float(os.environ.get("SP1_TIMER_DEBUG_REFRESH", "30"))
    )
