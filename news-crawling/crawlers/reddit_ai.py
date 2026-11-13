import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

from ._html_text import feed_content_to_text

logger = logging.getLogger(__name__)

_FEED_URLS = [
    "https://www.reddit.com/r/LocalLLaMA/hot.rss",
    "https://www.reddit.com/r/singularity/hot.rss",
]

_REDDIT_HEADERS = {
    **CRAWL_HEADERS,
    "User-Agent": "news-crawling-project/1.0 (AI news reader)",
}


def fetch() -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    try:
        with httpx.Client(headers=_REDDIT_HEADERS, follow_redirects=True) as client:
            for feed_url in _FEED_URLS:
                feed_articles = _fetch_feed(client, feed_url)
                articles.extend(feed_articles)
                if len(articles) >= 10:
                    break
    except Exception as e:
        logger.error("Reddit AI 크롤링 실패: %s", e)
        return []
    return articles[:10]


def _fetch_feed(client: httpx.Client, feed_url: str) -> list[dict[str, Any]]:
    try:
        resp = client.get(feed_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Reddit 피드 요청 실패 (%s): %s", feed_url, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    entries = soup.find_all("entry")
    items: list[dict[str, Any]] = []

    for entry in entries:
        title = _extract_tag_text(entry, "title")
        url = _extract_url(entry)
        if not title or not url:
            continue

        if _is_sticky(entry, title):
            continue

        published_at = (
            _extract_tag_text(entry, "updated")
            or _extract_tag_text(entry, "published")
            or datetime.now().isoformat()
        )

        cleaned_content = _extract_content_text(entry)

        if len(cleaned_content) < 30:
            content = f"{title}\n{cleaned_content}".strip()
        else:
            content = cleaned_content
        content = content[:8000]

        items.append({
            "url": url,
            "source": "Reddit AI",
            "title": title,
            "content": content,
            "published_at": published_at,
            "crawled_at": datetime.now().isoformat(),
            "major_category": "AI",
            "sub_category": "커뮤니티",
            "translate_to_korean": True,
        })

        if len(items) >= 5:
            break

    return items


def _is_sticky(entry: Any, title: str) -> bool:
    title_lower = title.lower()
    sticky_keywords = [
        "megathread",
        "daily discussion",
        "weekly discussion",
        "monthly discussion",
        "rules and guidelines",
        "[pinned]",
        "pinned post",
    ]
    if any(kw in title_lower for kw in sticky_keywords):
        return True

    for cat in entry.find_all("category"):
        term = str(cat.get("term", "")).lower()
        label = str(cat.get("label", "")).lower()
        if any(k in term or k in label for k in ("sticky", "pinned", "rules", "announcement")):
            return True

    return False


def _extract_url(entry: Any) -> str:
    link = entry.find("link")
    if link:
        href = link.get("href")
        if href:
            return str(href).strip()
        text = link.get_text(strip=True)
        if text:
            return text
    id_tag = entry.find("id")
    if id_tag:
        text = id_tag.get_text(strip=True)
        if text.startswith("http://") or text.startswith("https://"):
            return text
    return ""


def _extract_tag_text(entry: Any, tag_name: str) -> str:
    tag = entry.find(tag_name)
    return tag.get_text(strip=True) if tag else ""


def _extract_content_text(entry: Any) -> str:
    return feed_content_to_text(entry.find("content"))
