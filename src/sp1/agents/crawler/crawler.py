from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from datetime import datetime, timezone

import feedparser
import newspaper
from feedparser.util import FeedParserDict
from newspaper import network
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour, PeriodicBehaviour
from spade.message import Message

from sp1.agents.crawler.constants import MAX_ARTICLES_PER_CRAWL, ONTOLOGY_CRAWLER
from sp1.agents.crawler.models import ArticleModel, NormalizedArticleModel
from sp1.agents.crawler.models.crawler_outcome import (
    ArticlesOutcome,
    CrawlerOutcome,
    HealthStatus,
    SourceHealthPayload,
    SourceUnavailableOutcome,
)
from sp1.agents.crawler.models.crawler_params import CrawlerParams
from sp1.constants import TIME_FORMAT, USER_AGENT
from sp1.utils.logger import get_logger


class CrawlerAgent(Agent):
    """Crawler for one assigned RSS source. Supports on-demand and periodic crawls."""

    def __init__(self, params: CrawlerParams) -> None:
        super().__init__(params.jid, params.password)
        self.log = get_logger(str(self.jid))

        self._source_id = params.source_id
        self._rss_url = params.rss_url

        if params.newspaper_config is not None:
            self._config = params.newspaper_config
        else:
            self._config = newspaper.Config()
            self._config.browser_user_agent = USER_AGENT

        self.poll_interval_seconds = params.poll_interval_seconds

        self.blackboard = params.blackboard
        self._editor_jid = params.editor_jid

        self._seen_urls: set[str] = set()
        self._last_known_health: HealthStatus | None = None

        self.crawl_outcome: CrawlerOutcome | None = None

    ##############################
    # Source Health
    ##############################
    def _source_unavailable(self, reason: str) -> SourceUnavailableOutcome:
        return SourceUnavailableOutcome(rss_url=self._rss_url, reason=reason)

    def _source_health_from_outcome(self, outcome: CrawlerOutcome) -> HealthStatus:
        return "unavailable" if isinstance(outcome, SourceUnavailableOutcome) else "healthy"

    def _should_notify_source_health_change(self, new_health: HealthStatus) -> bool:
        if self._last_known_health is None:
            return new_health == "unavailable"
        return self._last_known_health != new_health

    async def _notify_editor_source_health(
        self,
        new_health: HealthStatus,
        reason: str,
        behaviour: CyclicBehaviour,
    ) -> None:
        if not self._should_notify_source_health_change(new_health):
            return

        msg = Message(to=self._editor_jid)

        msg.set_metadata("performative", "inform")
        msg.set_metadata("ontology", ONTOLOGY_CRAWLER)

        payload = SourceHealthPayload(source_id=self._source_id, status=new_health, reason=reason)
        msg.body = json.dumps(payload.model_dump())

        await behaviour.send(msg)

    ##############################

    def _entry_plain(self, value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict) and "value" in value:
            return str(value.get("value", "")).strip()

        # Fallback to force casting if we don't expect the type
        return str(value).strip()

    def _entry_link(self, entry: FeedParserDict) -> str:
        """
        Optimistic attempt to retrieve the source (link) of an entry
        from a parsed RSS feed.

        :param FeedParserDict entry: The entry to process.
        :return str: The link URL when one can be resolved, else empty string.
        """
        link = entry.get("link")

        if link:
            return self._entry_plain(link)

        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            candidate = entry_id.strip()
            if candidate:
                lower = candidate.lower()
                if lower.startswith(("http://", "https://")):
                    return candidate

        for link_rec in entry.get("links", []) or []:
            href = (link_rec.get("href") or "").strip()
            if not href:
                continue
            rel = (link_rec.get("rel") or "alternate").lower()
            if rel in ("alternate", "self"):
                return href

        return ""

    def _parse_feed_items(self, rss_xml: str) -> tuple[list[ArticleModel], str | None]:
        """
        Parse RSS/Atom with feedparser.

        First it attempts to retrieve the items from the feed; if no items
        were collected, this method verifies if a `bozo` exception is present
        and returns that exception too.

        :param str rss_xml: The string form of the RSS/Atom feed.
        :return: Parsed ``ArticleModel`` rows and optionally a parse error if ``bozo``.
        """
        parsed = feedparser.parse(rss_xml)
        items: list[ArticleModel] = []

        for entry in parsed.entries:
            url = self._entry_link(entry)
            if not url:
                continue

            title = self._entry_plain(entry.get("title"))
            summary = self._entry_plain(entry.get("summary") or entry.get("description"))
            author = self._entry_plain(entry.get("author"))

            categories = []
            for tag in entry.get("tags", []):
                term = tag.get("term")
                if term:
                    categories.append(self._entry_plain(term))

            published_at = ""
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                with contextlib.suppress(Exception):
                    published_at = TIME_FORMAT(entry.published_parsed)

            if not published_at:
                published_at = entry.get("published") or entry.get("updated") or ""
                if isinstance(published_at, str):
                    published_at = published_at.strip()

            items.append(
                ArticleModel(
                    url=url,
                    title=title,
                    summary=summary,
                    author=author,
                    categories=categories,
                    published_at=published_at,
                )
            )

        if not items and getattr(parsed, "bozo", False):
            exc = getattr(parsed, "bozo_exception", None)
            return [], (str(exc) if exc else "RSS parse error (feedparser bozo)")
        return items, None

    def _load_feed_items(self) -> list[ArticleModel] | SourceUnavailableOutcome:
        """
        Loads feed items from the assigned RSS/Atom feed.

        :return list[ArticleModel] | SourceUnavailableOutcome: The parsed feed items from the RSS/Atom feed.
        """
        try:
            rss_xml, status, _ = network.get_html_status(self._rss_url, self._config)
        except Exception as e:
            return self._source_unavailable(f"Failed to fetch RSS: {e}")

        if not rss_xml.strip():
            return self._source_unavailable(f"Empty RSS response (HTTP {status})")

        items, parse_err = self._parse_feed_items(rss_xml)
        if parse_err is not None:
            return self._source_unavailable(parse_err)

        return items

    def _download_normalized_articles(self, feed_items: list[ArticleModel]) -> list[NormalizedArticleModel]:
        """
        Downloads the articles from the RSS/Atom feed and parses them, attempting
        to normalize the final result according to the ``NormalizedArticleModel`` schema.

        :param list[ArticleModel] feed_items: The RSS/Atom feed collected items.
        :return list[NormalizedArticleModel]: The list of articles normalized according to the specified schema.
        """
        articles: list[NormalizedArticleModel] = []

        for item in feed_items[:MAX_ARTICLES_PER_CRAWL]:
            url = item.url
            if url in self._seen_urls:
                continue

            title_hint = item.title or ""
            art = newspaper.Article(url, config=self._config, title=title_hint)

            try:
                art.download()
                art.parse()
            except Exception as e:
                self.log.debug("article download/parse skipped url=%s err=%s", url, e)
                continue

            if not art.is_valid_body():
                continue

            self._seen_urls.add(url)

            fetched_at = datetime.now(timezone.utc).isoformat()

            body = art.text
            final_title = art.title if art.title else title_hint

            final_author = item.author
            if not final_author and art.authors:
                final_author = ", ".join(art.authors)

            final_pub_date = item.published_at
            if not final_pub_date and getattr(art, "publish_date", None):
                with contextlib.suppress(Exception):
                    final_pub_date = art.publish_date.isoformat()

            articles.append(
                NormalizedArticleModel(
                    article_id=hashlib.md5(f"{self._source_id}_{url}".encode(), usedforsecurity=False).hexdigest(),
                    source_id=self._source_id,
                    title=final_title,
                    body=body,
                    summary=item.summary or "",
                    url=url,
                    published_at=final_pub_date or "",
                    fetched_at=fetched_at,
                    categories=list(item.categories),
                    author=final_author or "",
                )
            )

        return articles

    async def _handle_crawl_outcome(self, outcome: CrawlerOutcome, behaviour: CyclicBehaviour) -> None:
        self.crawl_outcome = outcome

        new_health = self._source_health_from_outcome(outcome)
        reason = outcome.reason if isinstance(outcome, SourceUnavailableOutcome) else ""

        if isinstance(outcome, ArticlesOutcome) and outcome.articles:
            await self.blackboard.add_articles([a.model_dump() for a in outcome.articles])

        await self.blackboard.update_source_health(self._source_id, new_health, reason)
        await self._notify_editor_source_health(new_health, reason, behaviour)
        self._last_known_health = new_health

    def crawl(self) -> CrawlerOutcome:
        result = self._load_feed_items()
        if isinstance(result, SourceUnavailableOutcome):
            return result

        normalized = self._download_normalized_articles(result)
        return ArticlesOutcome(rss_url=self._rss_url, articles=normalized)

    class RSSFetchBehaviour(OneShotBehaviour):
        async def on_start(self) -> None:
            self.agent.log.info("Crawl one-shot: %s", self.agent._rss_url)

        async def run(self) -> None:
            outcome = await asyncio.to_thread(self.agent.crawl)
            await self.agent._handle_crawl_outcome(outcome, self)
            if isinstance(outcome, SourceUnavailableOutcome):
                self.exit_code = 1

    class PollFeedBehaviour(PeriodicBehaviour):
        async def run(self) -> None:
            self.agent.log.info("Polling feed: %s", self.agent._rss_url)
            outcome = await asyncio.to_thread(self.agent.crawl)
            await self.agent._handle_crawl_outcome(outcome, self)

    async def setup(self) -> None:
        self.log.info("CrawlerAgent %s starting...", self.jid)

        self.poll_feed_behaviour = self.PollFeedBehaviour(period=self.poll_interval_seconds)
        self.add_behaviour(self.poll_feed_behaviour)


if __name__ == "__main__":
    import os
    import signal

    import spade

    from sp1.agents.crawler.config import get_crawler_config
    from sp1.agents.crawler.crawler_builder import CrawlerBuilder
    from sp1.infra.blackboard import Blackboard

    crawler_config = get_crawler_config()

    def _write_results_json(path: str, payload: list) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)

    async def run_crawlers(spade_server: str) -> None:
        blackboard = Blackboard()
        editor_jid = f"editor@{spade_server}"

        crawlers = []
        for rss_feed in crawler_config.rss_feeds:
            name = rss_feed.name
            feed_url = rss_feed.feed

            source_id = hashlib.md5(feed_url.encode(), usedforsecurity=False).hexdigest()
            crawler = (
                CrawlerBuilder()
                .with_credentials(jid=f"crawler_{name}@{spade_server}", password=rss_feed.password)
                .with_source(source_id=source_id, rss_url=feed_url)
                .with_blackboard(blackboard)
                .with_editor_jid(editor_jid)
                .with_poll_interval_seconds(60)
                .build()
            )
            crawlers.append(crawler)
            await crawler.start(auto_register=True)
            print(f"Crawler {crawler.jid} started.")

        try:
            while True:
                await asyncio.sleep(10)
                all_results = await blackboard.snapshot_candidate_pool()
                await asyncio.to_thread(_write_results_json, "results.json", all_results)
                print(f"Updated results.json with {len(all_results)} articles.")

        except asyncio.CancelledError:
            print("Stopping crawlers...")
        finally:
            for crawler in crawlers:
                await crawler.stop()
                print(f"Crawler {crawler.jid} stopped.")

    async def main() -> None:
        spade_server = os.environ.get("SPADE_SERVER", "localhost")

        loop = asyncio.get_running_loop()
        main_task = asyncio.create_task(run_crawlers(spade_server))

        def shutdown() -> None:
            main_task.cancel()

        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, shutdown)

        with contextlib.suppress(asyncio.CancelledError):
            await main_task

    spade.run(main())
