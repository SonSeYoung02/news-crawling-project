import hashlib
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)


def _get_active_db_path() -> Path:
    return Path(os.environ.get("DB_PATH", str(DB_PATH)))


def init_db() -> None:
    with _connect() as conn:
        # 1. 기사 원문 테이블
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                url            TEXT UNIQUE NOT NULL,
                source         TEXT NOT NULL,
                title          TEXT NOT NULL,
                content        TEXT NOT NULL,
                published_at   TEXT,
                crawled_at     TEXT NOT NULL,
                summary        TEXT,
                major_category TEXT,
                sub_category   TEXT,
                tags           TEXT
            )
        """)
        # 2. 기존 분석 결과 테이블 (이전 데이터 보존용)
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
        # 3. 한국어 번역 테이블 (신규)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS article_translations (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id         INTEGER NOT NULL REFERENCES articles(id),
                content_hash       TEXT NOT NULL,
                translated_title   TEXT,
                translated_content TEXT,
                language           TEXT NOT NULL DEFAULT 'ko',
                status             TEXT NOT NULL DEFAULT 'pending',
                attempts           INTEGER NOT NULL DEFAULT 0,
                completed_at       TEXT,
                model              TEXT,
                last_error         TEXT,
                created_at         TEXT NOT NULL,
                updated_at         TEXT NOT NULL,
                UNIQUE(article_id, content_hash)
            )
        """)
        # 4. 긴 본문 분할 조각(Chunks) 테이블 (신규)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_chunks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id       INTEGER NOT NULL REFERENCES articles(id),
                content_hash     TEXT NOT NULL,
                chunk_index      INTEGER NOT NULL,
                total_chunks     INTEGER NOT NULL,
                original_chunk   TEXT NOT NULL,
                translated_chunk TEXT,
                status           TEXT NOT NULL DEFAULT 'pending',
                completed_at     TEXT,
                UNIQUE(article_id, content_hash, chunk_index)
            )
        """)
        # 5. 일일 무료 호출 한도 및 사용량 추적 테이블 (신규)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS translation_quota (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT UNIQUE NOT NULL,
                request_count   INTEGER NOT NULL DEFAULT 0,
                token_count     INTEGER NOT NULL DEFAULT 0,
                last_request_at TEXT
            )
        """)
        # 6. 프로세스 중복 실행 방지 락 테이블 (신규)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_locks (
                name        TEXT PRIMARY KEY,
                acquired_at TEXT NOT NULL,
                pid         INTEGER NOT NULL,
                info        TEXT
            )
        """)

        # 인덱스 생성
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_crawled_at ON articles(crawled_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_translations_status ON article_translations(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_translations_article_id ON article_translations(article_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_lookup ON translation_chunks(article_id, content_hash)")
        conn.commit()


@contextmanager
def _connect():
    db_file = _get_active_db_path()
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def compute_content_hash(title: str, content: str) -> str:
    """원문 제목과 본문의 해시를 생성하여 원문 변경 여부를 판별한다."""
    normalized = f"{(title or '').strip()}\n{(content or '').strip()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


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


def save_article(article: dict) -> bool:
    """원문을 articles 테이블에 저장한다. 성공 시 True, 중복 시 False."""
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


def refresh_article_from_source(article: dict) -> bool:
    """이미 수집된 URL에 대해 출처에서 가져온 최신 원문 및 메타데이터로 갱신한다.
    빈 본문으로 기존 정상 본문을 덮어쓰지 않는다."""
    with _connect() as conn:
        try:
            content = article.get("content", "")
            is_fallback = bool(article.get("content_is_fallback"))
            conn.execute("""
                UPDATE articles
                SET title = ?,
                    content = CASE
                        WHEN ? != '' AND (? = 0 OR COALESCE(content, '') = '') THEN ?
                        ELSE content
                    END,
                    source = ?,
                    published_at = COALESCE(?, published_at),
                    major_category = COALESCE(?, major_category),
                    sub_category = COALESCE(?, sub_category),
                    tags = ?
                WHERE url = ?
            """, (
                article.get("title", ""),
                content,
                is_fallback,
                content,
                article.get("source", ""),
                article.get("published_at"),
                article.get("major_category"),
                article.get("sub_category"),
                json.dumps(article.get("tags", []), ensure_ascii=False),
                article["url"]
            ))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("원문 갱신 실패 url=%s: %s", article.get("url"), e)
            return False


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
            SET content = ?
            WHERE url = ?
            """,
            (content, article["url"]),
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0


# --- 번역 관리 함수 ---

def get_or_create_translation(article_id: int, content_hash: str) -> dict:
    """해당 기사와 원문 해시에 대한 번역 레코드를 조회하거나 없으면 pending 상태로 생성한다."""
    now_str = datetime.now().isoformat()
    with _connect() as conn:
        row = conn.execute("""
            SELECT * FROM article_translations
            WHERE article_id = ? AND content_hash = ?
        """, (article_id, content_hash)).fetchone()

        if row:
            return dict(row)

        conn.execute("""
            INSERT OR IGNORE INTO article_translations
                (article_id, content_hash, language, status, attempts, created_at, updated_at)
            VALUES (?, ?, 'ko', 'pending', 0, ?, ?)
        """, (article_id, content_hash, now_str, now_str))
        conn.commit()

        row = conn.execute("""
            SELECT * FROM article_translations
            WHERE article_id = ? AND content_hash = ?
        """, (article_id, content_hash)).fetchone()
        return dict(row)


def save_translation_chunk(
    article_id: int,
    content_hash: str,
    chunk_index: int,
    total_chunks: int,
    original_chunk: str,
    translated_chunk: Optional[str] = None,
    status: str = "pending",
) -> bool:
    """본문 분할 조각의 번역 상태를 저장한다."""
    completed_at = datetime.now().isoformat() if status == "completed" else None
    with _connect() as conn:
        try:
            conn.execute("""
                INSERT INTO translation_chunks
                    (article_id, content_hash, chunk_index, total_chunks, original_chunk, translated_chunk, status, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id, content_hash, chunk_index) DO UPDATE SET
                    translated_chunk = excluded.translated_chunk,
                    status = excluded.status,
                    completed_at = excluded.completed_at
            """, (article_id, content_hash, chunk_index, total_chunks, original_chunk, translated_chunk, status, completed_at))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error("번역 청크 저장 실패 (article_id=%s, chunk=%d): %s", article_id, chunk_index, e)
            return False


def get_translation_chunks(article_id: int, content_hash: str) -> list[dict]:
    """해당 기사의 모든 번역 조각 목록을 순서대로 반환한다."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM translation_chunks
            WHERE article_id = ? AND content_hash = ?
            ORDER BY chunk_index ASC
        """, (article_id, content_hash)).fetchall()
        return [dict(r) for r in rows]


def complete_article_translation(
    article_id: int,
    content_hash: str,
    translated_title: str,
    translated_content: str,
    model: str,
) -> bool:
    """기사의 제목과 본문 번역이 완전히 끝났을 때 completed 상태로 갱신한다."""
    now_str = datetime.now().isoformat()
    with _connect() as conn:
        try:
            conn.execute("""
                UPDATE article_translations
                SET translated_title = ?,
                    translated_content = ?,
                    status = 'completed',
                    completed_at = ?,
                    model = ?,
                    updated_at = ?
                WHERE article_id = ? AND content_hash = ?
            """, (translated_title, translated_content, now_str, model, now_str, article_id, content_hash))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0
        except sqlite3.Error as e:
            logger.error("기사 번역 완료 갱신 실패 article_id=%s: %s", article_id, e)
            return False


def fail_article_translation(
    article_id: int,
    content_hash: str,
    error: str,
    max_attempts: int = 3,
) -> bool:
    """번역 시도 실패를 기록하고 시도 횟수를 증가시킨다. 최대 시도 초과 시 failed 상태로 전환."""
    now_str = datetime.now().isoformat()
    with _connect() as conn:
        try:
            row = conn.execute("""
                SELECT attempts FROM article_translations
                WHERE article_id = ? AND content_hash = ?
            """, (article_id, content_hash)).fetchone()
            attempts = (row["attempts"] if row else 0) + 1
            new_status = "failed" if attempts >= max_attempts else "pending"

            conn.execute("""
                UPDATE article_translations
                SET attempts = ?,
                    last_error = ?,
                    status = ?,
                    updated_at = ?
                WHERE article_id = ? AND content_hash = ?
            """, (attempts, error, new_status, now_str, article_id, content_hash))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error("번역 실패 기록 오류 article_id=%s: %s", article_id, e)
            return False


# --- 일일 무료 한도 추적 함수 ---

def get_daily_quota(date_str: str) -> dict:
    """지정된 날짜의 일일 호출 횟수와 토큰 사용량을 반환한다."""
    with _connect() as conn:
        row = conn.execute("""
            SELECT * FROM translation_quota WHERE date = ?
        """, (date_str,)).fetchone()
        if row:
            return dict(row)
        return {"date": date_str, "request_count": 0, "token_count": 0, "last_request_at": None}


def increment_daily_quota(date_str: str, requests: int = 1, tokens: int = 0) -> dict:
    """일일 사용량을 원자적으로 증가시키고 갱신된 사용량을 반환한다."""
    now_str = datetime.now().isoformat()
    with _connect() as conn:
        conn.execute("""
            INSERT INTO translation_quota (date, request_count, token_count, last_request_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                request_count = request_count + excluded.request_count,
                token_count = token_count + excluded.token_count,
                last_request_at = excluded.last_request_at
        """, (date_str, requests, tokens, now_str))
        conn.commit()
        row = conn.execute("SELECT * FROM translation_quota WHERE date = ?", (date_str,)).fetchone()
        return dict(row)


# --- 프로세스 락 관리 함수 ---

def acquire_crawl_lock(name: str = "nightly_crawl", timeout_minutes: int = 360) -> bool:
    """프로세스 상호 배제 락을 획득한다. 비정상 종료된 만료 락은 자동으로 회수한다."""
    now = datetime.now()
    now_str = now.isoformat()
    pid = os.getpid()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM crawl_locks WHERE name = ?", (name,)).fetchone()
        if row:
            try:
                acquired_time = datetime.fromisoformat(row["acquired_at"])
                if now - acquired_time > timedelta(minutes=timeout_minutes):
                    logger.warning("만료된 크롤러 락(%s, pid=%s, time=%s)을 회수합니다.", name, row["pid"], row["acquired_at"])
                    conn.execute("DELETE FROM crawl_locks WHERE name = ?", (name,))
                else:
                    logger.warning("이미 실행 중인 크롤러 프로세스가 존재합니다 (pid=%s, time=%s)", row["pid"], row["acquired_at"])
                    return False
            except Exception:
                conn.execute("DELETE FROM crawl_locks WHERE name = ?", (name,))

        try:
            conn.execute("""
                INSERT INTO crawl_locks (name, acquired_at, pid, info)
                VALUES (?, ?, ?, ?)
            """, (name, now_str, pid, f"Started at {now_str}"))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def release_crawl_lock(name: str = "nightly_crawl") -> bool:
    """크롤러 프로세스 락을 해제한다."""
    with _connect() as conn:
        conn.execute("DELETE FROM crawl_locks WHERE name = ?", (name,))
        conn.commit()
        return True


# --- 기존 분석 호환 함수 (보존) ---

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
