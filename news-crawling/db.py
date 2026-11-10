import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT UNIQUE NOT NULL,
                source       TEXT NOT NULL,
                title        TEXT NOT NULL,
                content      TEXT NOT NULL,
                published_at TEXT,
                crawled_at   TEXT NOT NULL,
                summary      TEXT,
                major_category TEXT,
                sub_category   TEXT,
                tags           TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_analysis (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id     INTEGER NOT NULL REFERENCES articles(id),
                summary        TEXT,
                major_category TEXT,
                sub_category   TEXT,
                tags           TEXT,
                analyzed_at    TEXT NOT NULL,
                UNIQUE(article_id)
            )
        """)
        conn.commit()


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def is_duplicate(url: str) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
        return row is not None


def get_article_by_url(url: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM articles WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None


def get_article_id_by_url(url: str) -> Optional[int]:
    with _connect() as conn:
        row = conn.execute("SELECT id FROM articles WHERE url = ?", (url,)).fetchone()
        return row["id"] if row else None


def save_analysis(
    article_id: int,
    summary: str,
    major_category: str,
    sub_category: str,
    tags: list,
) -> bool:
    tags_json = json.dumps(tags, ensure_ascii=False)
    with _connect() as conn:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO article_analysis
                    (article_id, summary, major_category, sub_category, tags, analyzed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    summary,
                    major_category,
                    sub_category,
                    tags_json,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("분석 결과 저장 실패 article_id=%s: %s", article_id, e)
            return False


def has_analysis(article_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM article_analysis WHERE article_id = ?", (article_id,)
        ).fetchone()
        return row is not None


def update_article_translation(article: dict) -> bool:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE articles
            SET title = ?, content = ?, summary = ?, major_category = ?, sub_category = ?, tags = ?, crawled_at = ?
            WHERE url = ?
            """,
            (
                article.get("title", ""),
                article.get("content", ""),
                article.get("summary"),
                article.get("major_category"),
                article.get("sub_category"),
                json.dumps(article.get("tags", []), ensure_ascii=False),
                article.get("crawled_at", datetime.now().isoformat()),
                article["url"],
            ),
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0


def update_content_if_empty(article: dict) -> bool:
    content = article.get("content", "")
    if not content:
        return False

    with _connect() as conn:
        row = conn.execute(
            "SELECT content FROM articles WHERE url = ?",
            (article["url"],),
        ).fetchone()
        if not row or row["content"]:
            return False

        conn.execute(
            """
            UPDATE articles
            SET content = ?, crawled_at = ?
            WHERE url = ?
            """,
            (
                content,
                article.get("crawled_at", datetime.now().isoformat()),
                article["url"],
            ),
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0


def save_article(article: dict) -> bool:
    """Returns True if saved, False if duplicate."""
    tags = article.get("tags", [])
    tags_json = json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else tags

    with _connect() as conn:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO articles
                    (url, source, title, content, published_at, crawled_at,
                     summary, major_category, sub_category, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article["url"],
                    article.get("source", ""),
                    article.get("title", ""),
                    article.get("content", ""),
                    article.get("published_at"),
                    article.get("crawled_at", datetime.now().isoformat()),
                    article.get("summary"),
                    article.get("major_category"),
                    article.get("sub_category"),
                    tags_json,
                ),
            )
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("DB 저장 실패 url=%s: %s", article.get("url"), e)
            return False


def save_articles_batch(articles: list[dict]) -> tuple[int, int]:
    """Returns (saved_count, skipped_count)."""
    saved = skipped = 0
    for article in articles:
        if save_article(article):
            saved += 1
        else:
            skipped += 1
    logger.info("저장: %d건, 중복 건너뜀: %d건", saved, skipped)
    return saved, skipped


def refresh_article_from_source(article: dict) -> bool:
    """이미 수집한 URL도 출처에서 가져온 원문과 메타데이터로 갱신한다."""
    with _connect() as conn:
        try:
            conn.execute("""
                UPDATE articles
                SET title = ?, content = CASE WHEN ? != '' AND (? = 0 OR COALESCE(content, '') = '') THEN ? ELSE content END,
                    source = ?, published_at = ?, crawled_at = ?,
                    major_category = ?, sub_category = ?, tags = ?
                WHERE url = ?
            """, (article.get("title", ""), article.get("content", ""), bool(article.get("content_is_fallback")), article.get("content", ""),
                  article.get("source", ""), article.get("published_at"),
                  article.get("crawled_at", datetime.now().isoformat()),
                  article.get("major_category"), article.get("sub_category"),
                  json.dumps(article.get("tags", []), ensure_ascii=False), article["url"]))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("원문 갱신 실패 url=%s: %s", article.get("url"), e)
            return False
