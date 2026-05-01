from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FilterRegisteredMessage(BaseModel):
    """Clerk → Editor / Analysts: a new (or updated) filter has been registered."""

    type: Literal["filter_registered"] = "filter_registered"
    filter_id: str = Field(..., description="Unique filter identifier.")
    user_id: str = Field(..., description="Owning user identifier.")
    mode: Literal["one_off", "standing"] = Field(..., description="Filter operating mode.")
    keywords: list[str] = Field(default_factory=list)
    keyword_mode: Literal["any", "all"] = Field(default="any")
    categories: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    max_age_hours: int | None = Field(default=None)
    min_credibility: float | None = Field(default=None)
    delivery: dict[str, int | float] = Field(default_factory=dict)
    created_at: str = Field(default="")


class FilterRemovedMessage(BaseModel):
    """Clerk → Editor: a standing filter has been removed."""

    type: Literal["filter_removed"] = "filter_removed"
    filter_id: str = Field(...)
    user_id: str = Field(...)


class BundleRequestMessage(BaseModel):
    """Clerk → Editor: synchronous one-off bundle request."""

    type: Literal["bundle_request"] = "bundle_request"
    request_id: str = Field(..., description="Client-side correlation id.")
    filter_id: str = Field(...)
    user_id: str = Field(...)
    reply_by: str | None = Field(default=None, description="ISO-8601 deadline for the response.")


class BundleDeliveryMessage(BaseModel):
    """Editor → Clerk: composed bundle ready for delivery."""

    type: Literal["bundle_delivery"] = "bundle_delivery"
    bundle_id: str = Field(...)
    filter_id: str = Field(...)
    user_id: str = Field(...)
    request_id: str | None = Field(default=None, description="Correlation id from the original BundleRequestMessage.")
    trigger: Literal["one_off", "standing_push"] = Field(...)
    composed_at: str = Field(default="")
    articles: list[dict[str, object]] = Field(
        default_factory=list, description="Per-article entries with summary and scores."
    )


class BundleFailureMessage(BaseModel):
    """Editor → Clerk: inability to compose a bundle."""

    type: Literal["bundle_failure"] = "bundle_failure"
    request_id: str | None = Field(default=None)
    filter_id: str = Field(...)
    user_id: str = Field(...)
    reason: str = Field(default="")


class FeedbackMessage(BaseModel):
    """Clerk → Analysts / Blackboard: user feedback on a delivered article."""

    type: Literal["feedback"] = "feedback"
    user_id: str = Field(...)
    article_id: str = Field(...)
    filter_id: str = Field(...)
    relevant: bool = Field(..., description="True if the user marked the article as relevant.")
    notes: str = Field(default="")
    submitted_at: str = Field(default="")


class SourceHealthMessage(BaseModel):
    """Crawler → Editor: source health update (reuses the model from crawler outcomes)."""

    type: Literal["source_health"] = "source_health"
    source_id: str = Field(...)
    status: Literal["healthy", "unavailable"]
    reason: str = Field(default="")
