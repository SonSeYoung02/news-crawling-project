import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_BASE_URL = "https://news.naver.com"
_SECTION_URLS = [
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=105",  # IT/과학
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=101",  # 경제
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=100",  # 정치
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=102",  # 사회
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=107",  # 연예
    "https://news.naver.com/main/main.naver?mode=LSD&mid=shm&sid1=001",  # 국제
]


def _fetch_article_content(client: httpx.Client, url: str) -> str:
    try:
        resp = client.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        article_body = (
            soup.select_one("#dic_area")
            or soup.select_one("#articleBodyContents")
            or soup.select_one(".article_body")
        )
        if article_body:
            return article_body.get_text(separator="\n", strip=True)
        return ""
    except Exception as e:
        logger.debug("기사 본문 수집 실패 url=%s: %s", url, e)
        return ""


def fetch() -> list[dict[str, Any]]:
    articles: list[dict] = []
    seen_urls: set[str] = set()

    try:
        with httpx.Client(headers=CRAWL_HEADERS, follow_redirects=True) as client:
            for section_url in _SECTION_URLS:
                try:
                    resp = client.get(section_url, timeout=REQUEST_TIMEOUT)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "lxml")

                    links = soup.select("a[href*='article']")
                    for link in links[:5]:  # 섹션당 최대 5건
                        href = link.get("href", "")
                        if not href.startswith("http"):
                            href = _BASE_URL + href
                        if href in seen_urls or "article" not in href:
                            continue
                        seen_urls.add(href)

                        title = link.get_text(strip=True)
                        if len(title) < 5:
                            continue

                        content = _fetch_article_content(client, href)
                        if not content:
                            continue

                        articles.append({
                            "url": href,
                            "source": "네이버뉴스",
                            "title": title,
                            "content": content,
                            "published_at": datetime.now().isoformat(),
                            "crawled_at": datetime.now().isoformat(),
                        })
                except Exception as e:
                    logger.error("네이버 섹션 수집 실패 url=%s: %s", section_url, e)
    except Exception as e:
        logger.error("네이버 크롤러 초기화 실패: %s", e)

    return articles
