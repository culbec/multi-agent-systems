from __future__ import annotations

from pydantic import BaseModel, Field


class ArticleModel(BaseModel):
    """Partial article extracted from one RSS/Atom entry (before HTML download)."""

    url: str = Field(
        ...,
        min_length=1,
        description=(
            "Canonical article URL resolved from the entry's link, permanent id (when it is "
            "already an http(s) URL), or the first alternate/self link in Atom-style link lists."
        ),
    )
    title: str = Field(
        default="",
        description="Entry title from the feed; may be empty if the publisher omitted it.",
    )
    summary: str = Field(
        default="",
        description="Short text from the entry's summary or description element, if any.",
    )
    author: str = Field(
        default="",
        description="Single author string from the feed entry when provided.",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Category terms collected from feed tags (e.g. Atom category @term).",
    )
    published_at: str = Field(
        default="",
        description=(
            "Best-effort publication time: UTC 'Z' string from structured published_parsed when "
            "available, otherwise the raw published or updated string from the entry."
        ),
    )


class NormalizedArticleModel(ArticleModel):
    """Full article record produced after RSS metadata plus newspaper HTML fetch/parse."""

    article_id: str = Field(
        description="Unique id (UUID string) for this article in the shared candidate pool.",
    )
    source_id: str = Field(
        ...,
        description="Logical source id of the crawler instance (ties the article to one feed).",
    )
    body: str = Field(
        ...,
        description="Main plain-text body extracted by newspaper4k after download and parse.",
    )
    fetched_at: str = Field(
        ...,
        description="UTC instant (ISO8601) when this normalized record was assembled.",
    )
    embedding: list[float] = Field(
        default_factory=list,
        description="Reserved for future dense embeddings; empty until an embedder populates it.",
    )
