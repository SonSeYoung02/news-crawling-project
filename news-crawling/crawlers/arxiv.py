import logging
import time
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS

logger = logging.getLogger(__name__)

_API_URL = (
    "https://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI"
    "&sortBy=submittedDate"
    "&sortOrder=descending"
    "&max_results=10"
)
_TIMEOUT = 30
_HEADERS = {
    **CRAWL_HEADERS,
    "User-Agent": "news-crawling-project/1.0 (contact: local-dev@example.com)",
}


def fetch() -> list[dict[str, Any]]:
    try:
        resp = _get_with_retry()
        resp.raise_for_status()
    except Exception as e:
        logger.error("arXiv API 크롤링 실패: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    articles = []
    for entry in soup.find_all("entry"):
        title = _tag_text(entry, "title")
        summary = _tag_text(entry, "summary")
        url = _entry_url(entry)
        if not title or not url:
            continue

        articles.append({
            "url": url,
            "source": "arXiv",
            "title": title,
            "content": summary,
            "published_at": _tag_text(entry, "published") or datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
            "major_category": "AI",
            "translate_to_korean": True,
        })
    return articles


def _get_with_retry() -> httpx.Response:
    last_response = None
    for attempt in range(3):
        if attempt:
            time.sleep(3)
        last_response = httpx.get(_API_URL, headers=_HEADERS, timeout=_TIMEOUT)
        if last_response.status_code != 429:
            return last_response
    return last_response


def _tag_text(entry, name: str) -> str:
    tag = entry.find(name)
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def _entry_url(entry) -> str:
    for link in entry.find_all("link"):
        if link.get("rel") == "alternate" and link.get("href"):
            return link["href"]
    entry_id = _tag_text(entry, "id")
    return entry_id
