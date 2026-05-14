import json
import re
from datetime import datetime
from html import unescape
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT


def fetch_rss(url: str, source_name: str) -> list[dict[str, Any]]:
    with httpx.Client(headers=CRAWL_HEADERS, follow_redirects=True) as client:
        resp = client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return _parse(resp.text, source_name, client)


def _parse(xml_text: str, source_name: str, client: httpx.Client) -> list[dict[str, Any]]:
    soup = BeautifulSoup(xml_text, "lxml-xml")
    articles = []
    for item in soup.find_all("item")[:10]:
        title = item.find("title")
        link = item.find("link")
        if not title or not link:
            continue
        url = link.get_text(strip=True)
        pub_date = item.find("pubDate")
        description = item.find("description")
        description_text = BeautifulSoup(
            description.get_text(strip=True) if description else "",
            "html.parser",
        ).get_text()
        article_content = _fetch_article_content(client, url)
        articles.append({
            "url": url,
            "source": source_name,
            "title": title.get_text(strip=True),
            "content": article_content or description_text,
            "published_at": pub_date.get_text(strip=True) if pub_date else datetime.now().isoformat(),
            "crawled_at": datetime.now().isoformat(),
        })
    return articles


def _fetch_article_content(client: httpx.Client, url: str) -> str:
    try:
        resp = client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return ""
    return _extract_article_content(resp.text)


def _extract_article_content(html_text: str) -> str:
    soup = BeautifulSoup(html_text, "lxml")
    selectors = [
        "div.article-text",
        "#dic_area",
        "#articleBodyContents",
        "#article_body",
        ".article_body",
        ".article-body",
        ".article_view",
        ".news_view",
        "article",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if not node:
            continue
        for removable in node.select("script, style, iframe, figure, .ad, .advertisement"):
            removable.decompose()
        text = _clean_text(node.get_text(separator="\n", strip=True))
        if len(text) >= 100:
            return text

    return _extract_script_content(html_text)


def _extract_script_content(html_text: str) -> str:
    values = []
    for match in re.finditer(r'"type":"text","content":"((?:\\.|[^"\\])*)"', html_text):
        try:
            values.append(json.loads(f'"{match.group(1)}"'))
        except json.JSONDecodeError:
            values.append(unescape(match.group(1)))
    return _clean_text("\n".join(values))


def _clean_text(text: str) -> str:
    blocked_lines = {"\uad11\uace0"}
    lines = [line.strip() for line in unescape(text).splitlines()]
    lines = [line for line in lines if all(blocked not in line for blocked in blocked_lines)]
    return "\n".join(line for line in lines if line)
