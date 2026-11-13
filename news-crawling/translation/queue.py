import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from config import KOREAN_RATIO_THRESHOLD
from db import _connect, compute_content_hash

logger = logging.getLogger(__name__)

KOREAN_SOURCES = {"네이버뉴스", "geeknews", "naver"}


def is_translatable_source(source: str) -> bool:
    """한국어 고유 소스(네이버뉴스, 긱뉴스 등)는 번역 대상에서 제외한다."""
    return (source or "").strip().lower() not in KOREAN_SOURCES


def is_korean_text(title: str, content: str, threshold: float = KOREAN_RATIO_THRESHOLD) -> bool:
    """제목 + 본문 앞 500자에서 공백 제외 글자 중 한글 비율이 threshold 이상이면 True."""
    text = "".join(((title or "") + (content or "")[:500]).split())
    if not text:
        return False
    korean = sum(1 for ch in text if "가" <= ch <= "힣")
    return korean / len(text) >= threshold


def _parse_timestamp(val: Optional[str]) -> float:
    """날짜 문자열을 UTC timestamp(float)로 변환한다. 파싱 불가 시 0.0 반환."""
    if not val or not val.strip():
        return 0.0
    text = val.strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        pass

    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def get_pending_translation_queue(new_article_ids: set[int]) -> list[dict]:
    """번역이 필요한 기사 대기열을 생성하고 우선순위에 따라 정렬하여 반환한다.
    - 한국어 소스 및 본문이 한국어인 기사는 제외
    - 현재 원문 해시와 일치하는 완료 번역이 이미 존재하면 제외
    - 우선순위 1: 당일 신규 수집된 기사 (new_article_ids 포함)
    - 우선순위 2: 이전 미완료 기사 및 원문 변경 기사
    - 각 그룹 내: 정규화된 발행시각(published_at) 내림차순, 수집시각(crawled_at) 내림차순, ID 오름차순
    """
    with _connect() as conn:
        rows = conn.execute("""
            SELECT id, url, source, title, content, published_at, crawled_at
            FROM articles
            ORDER BY id ASC
        """).fetchall()

        # 완료된 번역문 해시 맵 (article_id -> set of completed content_hashes)
        completed_rows = conn.execute("""
            SELECT article_id, content_hash
            FROM article_translations
            WHERE status = 'completed'
        """).fetchall()

    completed_map: dict[int, set[str]] = {}
    for r in completed_rows:
        completed_map.setdefault(r["article_id"], set()).add(r["content_hash"])

    queue = []
    for r in rows:
        article_id = r["id"]
        source = r["source"]

        # 1. 한국어 소스 제외
        if not is_translatable_source(source):
            continue

        title = r["title"] or ""
        content = r["content"] or ""

        # 1-2. 본문이 한국어이면 제외
        if is_korean_text(title, content):
            continue

        content_hash = compute_content_hash(title, content)

        # 2. 이미 현재 원문과 동일한 해시로 완료된 번역이 있으면 제외
        if content_hash in completed_map.get(article_id, set()):
            continue

        is_new = article_id in new_article_ids
        pub_time = _parse_timestamp(r["published_at"])
        crawl_time = _parse_timestamp(r["crawled_at"])
        effective_time = pub_time if pub_time > 0 else crawl_time

        job = {
            "article_id": article_id,
            "url": r["url"],
            "source": source,
            "title": title,
            "content": content,
            "content_hash": content_hash,
            "is_new_in_run": is_new,
            "published_at": r["published_at"],
            "crawled_at": r["crawled_at"],
            "_priority_group": 0 if is_new else 1,
            "_effective_time": effective_time,
            "_crawl_time": crawl_time,
        }
        queue.append(job)

    # 정렬: (우선순위 그룹 0 < 1, effective_time 내림차순, crawl_time 내림차순, article_id 오름차순)
    queue.sort(key=lambda j: (
        j["_priority_group"],
        -j["_effective_time"],
        -j["_crawl_time"],
        j["article_id"]
    ))

    # 내부 정렬 키 정리
    for j in queue:
        del j["_priority_group"]
        del j["_effective_time"]
        del j["_crawl_time"]

    logger.info("번역 대기열 생성 완료: 총 %d건 (신규 우선: %d건, 이전 잔여: %d건)",
                len(queue),
                sum(1 for j in queue if j["is_new_in_run"]),
                sum(1 for j in queue if not j["is_new_in_run"]))
    return queue
