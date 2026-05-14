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
