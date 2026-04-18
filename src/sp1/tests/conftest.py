from unittest.mock import AsyncMock, MagicMock

import pytest

from sp1.agents.crawler import CrawlerAgent
from sp1.tests.agents.crawler.support import MockBlackboard, build_crawler


@pytest.fixture
def mock_blackboard() -> MockBlackboard:
    return MockBlackboard()


@pytest.fixture
def mock_behaviour() -> MagicMock:
    b = MagicMock()
    b.send = AsyncMock()
    return b


@pytest.fixture
def crawler(mock_blackboard: MockBlackboard) -> CrawlerAgent:
    return build_crawler(mock_blackboard)
