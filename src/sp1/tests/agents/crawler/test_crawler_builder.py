import pytest
from pydantic import ValidationError

from sp1.agents.crawler import CrawlerBuilder
from sp1.tests.agents.crawler.support import MockBlackboard


def test_builder_requires_blackboard() -> None:
    b = CrawlerBuilder().with_credentials("a@localhost", "x").with_source("s", "http://u")
    with pytest.raises(ValidationError) as excinfo:
        b.build()
    locs = {tuple(e["loc"]) for e in excinfo.value.errors()}
    assert ("blackboard",) in locs
    assert ("editor_jid",) in locs


def test_builder_no_query_or_filters_fields() -> None:
    bb = MockBlackboard()
    agent = (
        CrawlerBuilder()
        .with_credentials(jid="c@localhost", password="password123")  # noqa: S106
        .with_source("src", "http://example.com/feed")
        .with_blackboard(bb)
        .with_editor_jid("editor@localhost")
        .with_poll_interval_seconds(60)
        .build()
    )
    assert not hasattr(agent, "_keywords")
    assert not hasattr(agent, "_query")
    assert not hasattr(agent, "_filters")
