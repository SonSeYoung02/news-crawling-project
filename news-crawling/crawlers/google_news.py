import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx
import trafilatura
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_BASE_URL = "https://news.google.com/rss/search"
_QUERIES = [
    ("global economy OR markets OR business", "경제"),
    ("artificial intelligence OR LLM OR generative AI", "AI"),
]


def fetch() -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    try:
        with httpx.Client(headers=CRAWL_HEADERS, follow_redirects=True) as client:
            for query, category in _QUERIES:
                articles.extend(_fetch_query(client, query, category, seen_urls))
    except Exception as e:
        logger.error("Google News 외국 뉴스 크롤링 실패: %s", e)
        return []
    return articles


def _fetch_query(
    client: httpx.Client,
    query: str,
    category: str,
    seen_urls: set[str],
) -> list[dict[str, Any]]:
    params = urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })
    resp = client.get(f"{_BASE_URL}?{params}", timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml-xml")
    articles = []
    for item in soup.find_all("item")[:10]:
        title = item.find("title")
        link = item.find("link")
        if not title or not link:
            continue

        url = link.get_text(strip=True)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        pub_date = item.find("pubDate")
        description = item.find("description")
        fallback = BeautifulSoup(
            description.get_text(" ", strip=True) if description else "",
            "html.parser",
        ).get_text(" ", strip=True)

        full_content = _fetch_article_content(client, url, "")
        content = full_content or fallback

        articles.append({
            "url": url,
            "source": "Google News",
            "title": title.get_text(strip=True),
            "content": content,
            "content_is_fallback": not bool(full_content),
            "published_at": pub_date.get_text(strip=True) if pub_date else datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
            "major_category": category,
        })
    return articles


def _fetch_article_content(client: httpx.Client, url: str, fallback: str) -> str:
    try:
        resp = client.get(url, timeout=15)
        resp.raise_for_status()
        content = trafilatura.extract(
            resp.text,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        if content and len(content) > 200:
            return content[:8000]
    except Exception as e:
        logger.warning("Google News 원문 추출 실패 (%s): %s", url[:80], e)
    return fallback
