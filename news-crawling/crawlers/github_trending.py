import logging
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import CRAWL_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

_TRENDING_URL = "https://github.com/trending?since=daily"

_AI_KEYWORDS = [
    "ai", "llm", "gpt", "agent", "model", "machine learning",
    "deep learning", "neural", "transformer", "diffusion",
    "rag", "mcp", "claude", "gemini", "openai", "ollama",
    "vllm", "langchain", "huggingface",
]
_AI_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _AI_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def fetch() -> list[dict[str, Any]]:
    try:
        resp = httpx.get(_TRENDING_URL, headers=CRAWL_HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return _parse_trending(resp.text)
    except Exception as e:
        logger.error("GitHub Trending 크롤링 실패: %s", e)
        return []


def _parse_trending(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "lxml")
    rows = soup.select("article.Box-row")
    if not rows:
        return []

    parsed_items: list[dict[str, Any]] = []
    for row in rows:
        item = _parse_row(row)
        if item:
            parsed_items.append(item)

    # Filter AI-related repositories first
    ai_items: list[dict[str, Any]] = []
    non_ai_items: list[dict[str, Any]] = []
    for it in parsed_items:
        if it.pop("_is_ai", False):
            ai_items.append(it)
        else:
            non_ai_items.append(it)

    if len(ai_items) < 5:
        # Fill with top trending repos up to 10 items
        needed = 10 - len(ai_items)
        result = ai_items + non_ai_items[:needed]
    else:
        result = ai_items[:10]

    return result


def _parse_row(row: Any) -> dict[str, Any] | None:
    link = row.select_one("h2 a[href]")
    if not link:
        return None

    href = link.get("href", "").strip()
    if not href:
        return None

    url = f"https://github.com{href}" if href.startswith("/") else href
    repo_name = href.strip("/")

    p_tag = row.find("p")
    description = p_tag.get_text(" ", strip=True) if p_tag else ""

    lang_tag = row.select_one("[itemprop='programmingLanguage']")
    lang = lang_tag.get_text(strip=True) if lang_tag else ""

    content_lines = [
        f"GitHub Repository: {repo_name}",
        f"URL: {url}",
    ]
    if description:
        content_lines.append(f"Description: {description}")
    if lang:
        content_lines.append(f"Language: {lang}")

    content = "\n".join(content_lines)
    if len(content) < 50:
        content = f"{content}\nGitHub daily trending open-source repository."

    title = f"{repo_name}: {description}" if description else repo_name
    is_ai = _is_ai_repo(repo_name, description)

    return {
        "url": url,
        "source": "GitHub Trending",
        "title": title,
        "content": content[:8000],
        "published_at": datetime.now().isoformat(),
        "crawled_at": datetime.now().isoformat(),
        "major_category": "AI",
        "sub_category": "오픈소스",
        "translate_to_korean": True,
        "_is_ai": is_ai,
    }


def _is_ai_repo(repo_name: str, description: str) -> bool:
    text = f"{repo_name} {description}"
    normalized = re.sub(r"[-_./]", " ", text)
    return bool(_AI_REGEX.search(normalized))
