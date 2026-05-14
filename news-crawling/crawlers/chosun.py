import logging
from typing import Any

from ._rss import fetch_rss

logger = logging.getLogger(__name__)

_RSS_URL = "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"


def fetch() -> list[dict[str, Any]]:
    try:
        return fetch_rss(_RSS_URL, "조선일보")
    except Exception as e:
        logger.error("조선일보 크롤링 실패: %s", e)
        return []
