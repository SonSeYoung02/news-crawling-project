import logging
from typing import Any

from ._rss import fetch_rss

logger = logging.getLogger(__name__)

_RSS_URL = "https://rss.joins.com/joins_news_list.xml"


def fetch() -> list[dict[str, Any]]:
    try:
        return fetch_rss(_RSS_URL, "중앙일보")
    except Exception as e:
        logger.error("중앙일보 크롤링 실패: %s", e)
        return []
