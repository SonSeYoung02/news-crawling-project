import logging
from typing import Any

from ._rss import fetch_rss

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.hani.co.kr/rss/"


def fetch() -> list[dict[str, Any]]:
    try:
        return fetch_rss(_RSS_URL, "한겨레")
    except Exception as e:
        logger.error("한겨레 크롤링 실패: %s", e)
        return []
