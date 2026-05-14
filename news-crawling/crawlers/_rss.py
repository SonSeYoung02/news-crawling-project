from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT


def fetch_rss(url: str, source_name: str) -> list[dict[str, Any]]:
    with httpx.Client(headers=CRAWL_HEADERS, follow_redirects=True) as client:
        resp = client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return _parse(resp.text, source_name)


def _parse(xml_text: str, source_name: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(xml_text, "lxml-xml")
    articles = []
    for item in soup.find_all("item")[:10]:
        title = item.find("title")
        link = item.find("link")
        if not title or not link:
            continue
        pub_date = item.find("pubDate")
        description = item.find("description")
        articles.append({
            "url": link.get_text(strip=True),
            "source": source_name,
            "title": title.get_text(strip=True),
            "content": BeautifulSoup(
                description.get_text(strip=True) if description else "",
                "html.parser",
            ).get_text(),
            "published_at": pub_date.get_text(strip=True) if pub_date else datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
        })
    return articles
