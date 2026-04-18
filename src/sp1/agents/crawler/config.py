import json
import os
import pathlib
from typing import Any

from pydantic import BaseModel, Field


class RSSFeed(BaseModel):
    name: str
    feed: str
    password: str
    poll_interval_seconds: int = 600
    seed_credibility: float = 0.5
    categories: list[str] = Field(default_factory=list)


class CrawlerConfig(BaseModel):
    rss_feeds: list[RSSFeed] = Field(
        default_factory=list,
        description="A collection of RSS/Atom feeds that will be assigned to a Crawler agent.",
        examples=[{"feed": "https://my-rss-feed.com/rss.xml", "password": "mypassword"}],
    )


def get_crawler_config() -> CrawlerConfig:
    config = CrawlerConfig()

    rss_feeds_path = os.environ.get("RSS_FEEDS_PATH")
    if rss_feeds_path is None:
        raise ValueError("Provided null RSS feeds path!")

    rss_feeds_path = pathlib.Path(rss_feeds_path).resolve()
    if not rss_feeds_path.exists():
        raise ValueError(f"The RSS feeds path '{rss_feeds_path}' does not exist!")

    with open(rss_feeds_path, "r") as fin:
        rss_feeds: dict[str, dict[str, Any]] = json.load(fin)
        for name, parameters in rss_feeds.items():
            raw_categories = parameters.get("categories")
            categories = list(raw_categories) if isinstance(raw_categories, list) else []
            config.rss_feeds.append(
                RSSFeed(
                    name=name,
                    feed=parameters.get("feed"),
                    password=parameters.get("password"),
                    poll_interval_seconds=parameters.get("poll_interval_seconds", 600),
                    seed_credibility=parameters.get("seed_credibility", 0.5),
                    categories=categories,
                )
            )

    return config
