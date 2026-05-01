from sp1.infra.config import SP1Config

_cfg = SP1Config()

POLL_INTERVAL_SEC: int = _cfg.interval_crawler_poll
MAX_ARTICLES_PER_CRAWL: int = _cfg.limit_max_articles_per_crawl
ONTOLOGY_CRAWLER: str = "news-aggregation-crawler"
