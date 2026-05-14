import logging
from datetime import datetime
from typing import Any

import httpx

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_API_URL = "https://dev.to/api/articles"
_PARAMS = {
    "tag": "ai",
    "per_page": 10,
    "top": 7,
}


def fetch() -> list[dict[str, Any]]:
    try:
        resp = httpx.get(_API_URL, params=_PARAMS, headers=CRAWL_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        logger.error("dev.to API 크롤링 실패: %s", e)
        return []

    articles = []
    for item in payload:
        title = item.get("title", "")
        url = item.get("url") or item.get("canonical_url")
        if not title or not url:
            continue

        articles.append({
            "url": url,
            "source": "dev.to",
            "title": title,
            "content": _content(item),
            "published_at": item.get("published_at") or datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
            "major_category": "IT",
            "sub_category": "개발",
            "tags": item.get("tag_list", [])[:10],
            "translate_to_korean": True,
        })
    return articles


def _content(item: dict[str, Any]) -> str:
    parts = [
        item.get("description", ""),
        item.get("readable_publish_date", ""),
    ]
    tags = item.get("tag_list") or []
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    return "\n".join(part for part in parts if part)
