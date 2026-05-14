import logging
from typing import Any

from .chosun import fetch as fetch_chosun
from .hankyoreh import fetch as fetch_hankyoreh
from .joongang import fetch as fetch_joongang
from .naver import fetch as fetch_naver

logger = logging.getLogger(__name__)

_SOURCES = [
    ("네이버뉴스", fetch_naver),
    ("조선일보", fetch_chosun),
    ("중앙일보", fetch_joongang),
    ("한겨레", fetch_hankyoreh),
]


def get_all_articles() -> list[dict[str, Any]]:
    """Collect articles from all sources, skipping failed sources."""
    all_articles: list[dict] = []
    for name, fetch_fn in _SOURCES:
        try:
            articles = fetch_fn()
            logger.info("%s: %d건 수집", name, len(articles))
            all_articles.extend(articles)
        except Exception as e:
            logger.error("%s 크롤링 실패: %s", name, e)
    return all_articles
