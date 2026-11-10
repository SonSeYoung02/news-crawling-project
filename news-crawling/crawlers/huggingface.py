import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_BLOG_FEED_URL = "https://huggingface.co/blog/feed.xml"
_PAPERS_URL = "https://huggingface.co/papers"


def fetch() -> list[dict[str, Any]]:
    try:
        articles = _fetch_blog_feed()
        if articles:
            return articles[:10]
        return _fetch_papers()[:10]
    except Exception as e:
        logger.error("Hugging Face 크롤링 실패: %s", e)
        return []


def _fetch_blog_feed() -> list[dict[str, Any]]:
    try:
        resp = httpx.get(_BLOG_FEED_URL, headers=CRAWL_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Hugging Face 블로그 피드 요청 실패: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml-xml")
    elements = soup.find_all("item")
    if not elements:
        elements = soup.find_all("entry")

    articles: list[dict[str, Any]] = []
    for el in elements[:10]:
        title = _extract_tag_text(el, "title")
        url = _extract_url(el)
        if not title or not url:
            continue

        published_at = (
            _extract_tag_text(el, "pubDate")
            or _extract_tag_text(el, "published")
            or _extract_tag_text(el, "updated")
            or datetime.now().isoformat()
        )

        raw_content = _extract_raw_content(el)
        cleaned_content = (
            BeautifulSoup(raw_content, "html.parser").get_text("\n", strip=True)
            if raw_content
            else ""
        )
        content = (cleaned_content or title)[:8000]

        articles.append({
            "url": url,
            "source": "Hugging Face",
            "title": title,
            "content": content,
            "published_at": published_at,
            "crawled_at": datetime.now().isoformat(),
            "major_category": "AI",
        })

    return articles


def _fetch_papers() -> list[dict[str, Any]]:
    try:
        resp = httpx.get(_PAPERS_URL, headers=CRAWL_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Hugging Face Papers 요청 실패: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    articles: list[dict[str, Any]] = []
    for link in soup.select("a[href^='/papers/']"):
        href = link.get("href", "")
        title_el = link.find(["h3", "h4", "p"]) or link
        title = title_el.get_text(strip=True)
        if not title or len(title) < 5 or href == "/papers":
            continue

        url = f"https://huggingface.co{href}"
        if any(a["url"] == url for a in articles):
            continue

        articles.append({
            "url": url,
            "source": "Hugging Face",
            "title": title,
            "content": f"Hugging Face Daily Paper: {title}\nURL: {url}",
            "published_at": datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
            "major_category": "AI",
        })
        if len(articles) >= 10:
            break

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


def _extract_raw_content(element: Any) -> str:
    for tag_name in ("description", "content", "summary"):
        tag = element.find(tag_name)
        if tag:
            try:
                contents = tag.decode_contents().strip()
                if contents:
                    return contents
            except Exception:
                pass
            text = tag.get_text(strip=True)
            if text:
                return text
    return ""
