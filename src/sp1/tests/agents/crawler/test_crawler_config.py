import json
import pathlib

from sp1.agents.crawler.config import RSSFeed, get_crawler_config


def test_get_crawler_config_reads_all_fields(tmp_path: pathlib.Path, monkeypatch) -> None:
    cfg_path = tmp_path / "feeds.json"
    cfg_path.write_text(
        json.dumps(
            {
                "bbc": {
                    "feed": "https://bbc.com/rss",
                    "password": "s3cr3t",
                    "poll_interval_seconds": 300,
                    "seed_credibility": 0.9,
                    "categories": ["world", "tech"],
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("RSS_FEEDS_PATH", str(cfg_path))
    config = get_crawler_config()
    assert len(config.rss_feeds) == 1
    feed = config.rss_feeds[0]
    assert isinstance(feed, RSSFeed)
    assert feed.poll_interval_seconds == 300
    assert feed.seed_credibility == 0.9
    assert feed.categories == ["world", "tech"]


def test_get_crawler_config_uses_defaults(tmp_path: pathlib.Path, monkeypatch) -> None:
    cfg_path = tmp_path / "feeds.json"
    cfg_path.write_text(
        json.dumps({"src": {"feed": "https://example.com/rss", "password": "x"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("RSS_FEEDS_PATH", str(cfg_path))
    config = get_crawler_config()
    feed = config.rss_feeds[0]
    assert feed.poll_interval_seconds == 600
    assert feed.seed_credibility == 0.5
    assert feed.categories == []
