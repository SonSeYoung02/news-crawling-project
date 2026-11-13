import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

from ._html_text import feed_content_to_text

logger = logging.getLogger(__name__)

_PRIMARY_FEED = "https://feeds.feedburner.com/geeknews-feed"
_FALLBACK_FEED = "https://news.hada.io/rss/news"


def fetch() -> list[dict[str, Any]]:
    try:
        xml_text = _fetch_feed_xml()
        if not xml_text:
            return []
        return _parse_feed(xml_text)
    except Exception as e:
        logger.error("GeekNews 크롤링 실패: %s", e)
        return []


def _fetch_feed_xml() -> str:
    with httpx.Client(headers=CRAWL_HEADERS, follow_redirects=True) as client:
        for feed_url in (_PRIMARY_FEED, _FALLBACK_FEED):
            try:
                resp = client.get(feed_url, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                if resp.text:
                    return resp.text
            except Exception as e:
                logger.warning("GeekNews 피드 요청 실패 (%s): %s", feed_url, e)
    return ""


def _parse_feed(xml_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(xml_text, "lxml-xml")
    elements = soup.find_all("entry")
    if not elements:
        elements = soup.find_all("item")

    articles: list[dict[str, Any]] = []
    for el in elements[:10]:
        title = _extract_tag_text(el, "title")
        url = _extract_url(el)
        if not title or not url:
            continue

        published_at = (
            _extract_tag_text(el, "published")
            or _extract_tag_text(el, "updated")
            or _extract_tag_text(el, "pubDate")
            or datetime.now().isoformat()
        )

        cleaned_content = _extract_content_text(el)
        content = (cleaned_content or title)[:8000]

        articles.append({
            "url": url,
            "source": "GeekNews",
            "title": title,
            "content": content,
            "published_at": published_at,
            "crawled_at": datetime.now().isoformat(),
            "major_category": "AI",
        })

    return articles


def _extract_url(element: Any) -> str:
    link = element.find("link")
    if link:
        href = link.get("href")
        if href:
            return str(href).strip()
        text = link.get_text(strip=True)
        if text:
            return text
    id_tag = element.find("id")
    if id_tag:
        text = id_tag.get_text(strip=True)
        if text.startswith("http://") or text.startswith("https://"):
            return text
    return ""


def _extract_tag_text(element: Any, tag_name: str) -> str:
    tag = element.find(tag_name)
    return tag.get_text(strip=True) if tag else ""


def _extract_content_text(element: Any) -> str:
    for tag_name in ("content", "summary", "description"):
        tag = element.find(tag_name)
        if tag:
            text = feed_content_to_text(tag)
            if text:
                return text
    return ""
