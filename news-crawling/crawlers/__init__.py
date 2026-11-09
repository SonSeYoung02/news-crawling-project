import logging
from typing import Any

from .arxiv import fetch as fetch_arxiv
from .devto import fetch as fetch_devto
from .geeknews import fetch as fetch_geeknews
from .github_trending import fetch as fetch_github_trending
from .google_news import fetch as fetch_google_news
from .huggingface import fetch as fetch_huggingface
from .naver import fetch as fetch_naver
from .reddit_ai import fetch as fetch_reddit_ai

logger = logging.getLogger(__name__)

_SOURCES = [
    ("네이버뉴스", fetch_naver),
    ("Google News", fetch_google_news),
    ("GeekNews", fetch_geeknews),
    ("Reddit AI", fetch_reddit_ai),
    ("GitHub Trending", fetch_github_trending),
    ("Hugging Face", fetch_huggingface),
    ("arXiv", fetch_arxiv),
    ("dev.to", fetch_devto),
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
