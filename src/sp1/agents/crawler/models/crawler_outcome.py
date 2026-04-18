from typing import Literal

from pydantic import BaseModel, Field

from sp1.agents.crawler.models import NormalizedArticleModel


class ArticlesOutcome(BaseModel):
    rss_url: str = Field(
        ...,
        description="URL of the RSS or Atom feed to poll.",
    )
    articles: list[NormalizedArticleModel] = Field(
        default_factory=list,
        description="The collected Articles from the RSS/Atom feed.",
    )


class SourceUnavailableOutcome(BaseModel):
    rss_url: str = Field(
        ...,
        description="URL of the RSS or Atom feed to poll.",
    )
    reason: str = Field(..., description="The reason of source unavailability.")


CrawlerOutcome = ArticlesOutcome | SourceUnavailableOutcome

HealthStatus = Literal["healthy", "unavailable"]


class SourceHealthPayload(BaseModel):
    type: Literal["source_health"] = "source_health"
    source_id: str = Field(
        ...,
        description="Logical source id of the crawler instance (ties the article to one feed).",
    )
    status: HealthStatus
    reason: str = Field(..., description="The reason of source unavailability.")
