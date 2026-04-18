from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sp1.agents.crawler.crawler import CrawlerAgent
    from sp1.agents.crawler.crawler_builder import CrawlerBuilder
    from sp1.agents.crawler.models.crawler_params import CrawlerParams

__all__ = ["CrawlerAgent", "CrawlerBuilder", "CrawlerParams"]


def __getattr__(name: str):
    if name == "CrawlerAgent":
        from sp1.agents.crawler.crawler import CrawlerAgent

        return CrawlerAgent
    if name == "CrawlerBuilder":
        from sp1.agents.crawler.crawler_builder import CrawlerBuilder

        return CrawlerBuilder
    if name == "CrawlerParams":
        from sp1.agents.crawler.models.crawler_params import CrawlerParams

        return CrawlerParams
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
