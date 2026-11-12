import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "news-crawling" / "news.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(DEFAULT_DB_PATH)))

app = FastAPI(
    title="News Viewer API",
    description="뉴스 크롤링 데이터를 조회하는 REST API. 기사 목록·상세·카테고리·출처 엔드포인트를 제공합니다.",
    version="1.0.0",
)


def compute_content_hash(title: str, content: str) -> str:
    """원문 제목과 본문의 해시를 생성하여 원문 변경 여부를 판별한다."""
    normalized = f"{(title or '').strip()}\n{(content or '').strip()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


class Article(BaseModel):
    id: int
    url: str
    source: str
    title: str
    content: Optional[str] = None
    published_at: Optional[str] = None
    crawled_at: Optional[str] = None
    summary: Optional[str] = None
    major_category: Optional[str] = None
    sub_category: Optional[str] = None
    tags: list[str] = []
    original_title: Optional[str] = None
    original_content: Optional[str] = None
    translated_title: Optional[str] = None
    translated_content: Optional[str] = None
    translation_status: Optional[str] = "pending"


class ArticleListResponse(BaseModel):
    total: int
    page: int
    size: int
    articles: list[Article]


class CategoryCount(BaseModel):
    major_category: str
    count: int


class SourceCount(BaseModel):
    source: str
    count: int

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>뉴스 뷰어 백엔드</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
    }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 48px 56px;
      text-align: center;
      max-width: 480px;
      width: 90%;
      box-shadow: 0 25px 50px rgba(0,0,0,0.4);
    }
    .dot {
      width: 14px; height: 14px;
      background: #22c55e;
      border-radius: 50%;
      display: inline-block;
      margin-right: 8px;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
      50% { box-shadow: 0 0 0 8px rgba(34,197,94,0); }
    }
    .status {
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      color: #22c55e;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 24px;
    }
    h1 {
      font-size: 28px;
      font-weight: 700;
      margin-bottom: 8px;
      color: #f1f5f9;
    }
    p {
      color: #94a3b8;
      font-size: 15px;
      margin-bottom: 32px;
    }
    .links {
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
    }
    a {
      display: inline-block;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 500;
      text-decoration: none;
      transition: background 0.2s;
    }
    .btn-primary {
      background: #3b82f6;
      color: #fff;
    }
    .btn-primary:hover { background: #2563eb; }
    .btn-secondary {
      background: #334155;
      color: #cbd5e1;
    }
    .btn-secondary:hover { background: #475569; }
    .info {
      margin-top: 32px;
      padding-top: 24px;
      border-top: 1px solid #334155;
      font-size: 13px;
      color: #64748b;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="status"><span class="dot"></span>백엔드 실행중</div>
    <h1>뉴스 뷰어 API</h1>
    <p>FastAPI 서버가 정상적으로 동작하고 있습니다.</p>
    <div class="links">
      <a href="/docs" class="btn-primary">Swagger 문서</a>
      <a href="/redoc" class="btn-secondary">ReDoc 문서</a>
      <a href="/articles" class="btn-secondary">기사 목록 API</a>
    </div>
    <div class="info">http://localhost:8000</div>
  </div>
</body>
</html>
"""


def _get_active_db_path() -> Path:
    return Path(os.environ.get("DB_PATH", str(DB_PATH)))


@contextmanager
def _connect():
    conn = sqlite3.connect(_get_active_db_path())
    conn.row_factory = sqlite3.Row
    conn.create_function("compute_content_hash", 2, compute_content_hash)
    try:
        yield conn
    finally:
        conn.close()


def _has_translations_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='article_translations'"
    ).fetchone()
    return row is not None


def _row_to_dict(row) -> dict:
    d = dict(row)
    tags = d.get("tags")
    if isinstance(tags, str):
        try:
            d["tags"] = json.loads(tags)
        except Exception:
            d["tags"] = []
    elif tags is None:
        d["tags"] = []
    return d


@app.get(
    "/articles",
    response_model=ArticleListResponse,
    summary="기사 목록 조회",
    description="크롤링된 뉴스 기사 목록을 페이지네이션으로 반환합니다. 카테고리·출처·키워드로 필터링할 수 있습니다. 번역 완료 기사는 한국어 번역문을 우선 제공합니다.",
    tags=["articles"],
)
def get_articles(
    page: int = Query(1, ge=1, description="페이지 번호 (1부터 시작)"),
    size: int = Query(20, ge=1, le=100, description="페이지당 기사 수 (최대 100)"),
    category: Optional[str] = Query(None, description="대분류 필터 (예: IT/과학, 경제)"),
    source: Optional[str] = Query(None, description="출처 필터 (예: devto, google_news)"),
    q: Optional[str] = Query(None, description="원문/번역 제목, 본문 또는 요약 검색어"),
):
    offset = (page - 1) * size

    with _connect() as conn:
        has_trans = _has_translations_table(conn)

        conditions = []
        params: list = []

        if category:
            conditions.append("COALESCE(aa.major_category, a.major_category) = ?")
            params.append(category)
        if source:
            conditions.append("a.source = ?")
            params.append(source)
        if q:
            if has_trans:
                conditions.append(
                    """(
                        a.title LIKE ?
                        OR (at.status = 'completed' AND at.translated_title LIKE ?)
                        OR a.content LIKE ?
                        OR (at.status = 'completed' AND at.translated_content LIKE ?)
                        OR COALESCE(aa.summary, a.summary) LIKE ?
                    )"""
                )
                params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
            else:
                conditions.append(
                    "(a.title LIKE ? OR a.content LIKE ? OR COALESCE(aa.summary, a.summary) LIKE ?)"
                )
                params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        if has_trans:
            base_query = f"""
                FROM articles a
                LEFT JOIN article_analysis aa ON aa.article_id = a.id
                LEFT JOIN article_translations at
                    ON at.article_id = a.id
                    AND at.content_hash = compute_content_hash(a.title, a.content)
                {where}
            """
            select_fields = """
                a.id, a.url, a.source,
                a.published_at, a.crawled_at,
                a.title AS original_title,
                a.content AS original_content,
                CASE
                    WHEN at.status = 'completed' AND at.translated_title IS NOT NULL AND at.translated_title != ''
                    THEN at.translated_title
                    ELSE a.title
                END AS title,
                CASE
                    WHEN at.status = 'completed' AND at.translated_content IS NOT NULL AND at.translated_content != ''
                    THEN at.translated_content
                    ELSE a.content
                END AS content,
                CASE
                    WHEN at.status = 'completed' THEN at.translated_title
                    ELSE NULL
                END AS translated_title,
                CASE
                    WHEN at.status = 'completed' THEN at.translated_content
                    ELSE NULL
                END AS translated_content,
                CASE
                    WHEN at.status IS NOT NULL THEN at.status
                    WHEN a.source IN ('naver', 'geeknews') THEN 'not_needed'
                    ELSE 'pending'
                END AS translation_status,
                COALESCE(aa.summary, a.summary) AS summary,
                COALESCE(aa.major_category, a.major_category) AS major_category,
                COALESCE(aa.sub_category, a.sub_category) AS sub_category,
                COALESCE(aa.tags, a.tags) AS tags
            """
        else:
            base_query = f"""
                FROM articles a
                LEFT JOIN article_analysis aa ON aa.article_id = a.id
                {where}
            """
            select_fields = """
                a.id, a.url, a.source,
                a.published_at, a.crawled_at,
                a.title AS original_title,
                a.content AS original_content,
                a.title AS title,
                a.content AS content,
                NULL AS translated_title,
                NULL AS translated_content,
                CASE
                    WHEN a.source IN ('naver', 'geeknews') THEN 'not_needed'
                    ELSE 'pending'
                END AS translation_status,
                COALESCE(aa.summary, a.summary) AS summary,
                COALESCE(aa.major_category, a.major_category) AS major_category,
                COALESCE(aa.sub_category, a.sub_category) AS sub_category,
                COALESCE(aa.tags, a.tags) AS tags
            """

        total = conn.execute(f"SELECT COUNT(*) {base_query}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT
                {select_fields}
            {base_query}
            ORDER BY a.crawled_at DESC LIMIT ? OFFSET ?
            """,
            params + [size, offset],
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "size": size,
        "articles": [_row_to_dict(r) for r in rows],
    }


@app.get(
    "/articles/{article_id}",
    response_model=Article,
    summary="기사 상세 조회",
    description="article_id로 단일 기사의 전체 정보를 반환합니다. 번역 완료 기사는 한국어 번역문을 우선 제공하며, 미번역 시 원문을 반환합니다. 존재하지 않으면 404를 반환합니다.",
    tags=["articles"],
)
def get_article(article_id: int):
    with _connect() as conn:
        has_trans = _has_translations_table(conn)
        if has_trans:
            row = conn.execute(
                """
                SELECT
                    a.id, a.url, a.source,
                    a.published_at, a.crawled_at,
                    a.title AS original_title,
                    a.content AS original_content,
                    CASE
                        WHEN at.status = 'completed' AND at.translated_title IS NOT NULL AND at.translated_title != ''
                        THEN at.translated_title
                        ELSE a.title
                    END AS title,
                    CASE
                        WHEN at.status = 'completed' AND at.translated_content IS NOT NULL AND at.translated_content != ''
                        THEN at.translated_content
                        ELSE a.content
                    END AS content,
                    CASE
                        WHEN at.status = 'completed' THEN at.translated_title
                        ELSE NULL
                    END AS translated_title,
                    CASE
                        WHEN at.status = 'completed' THEN at.translated_content
                        ELSE NULL
                    END AS translated_content,
                    CASE
                    WHEN at.status IS NOT NULL THEN at.status
                    WHEN a.source IN ('naver', 'geeknews') THEN 'not_needed'
                    ELSE 'pending'
                END AS translation_status,
                    COALESCE(aa.summary, a.summary) AS summary,
                    COALESCE(aa.major_category, a.major_category) AS major_category,
                    COALESCE(aa.sub_category, a.sub_category) AS sub_category,
                    COALESCE(aa.tags, a.tags) AS tags
                FROM articles a
                LEFT JOIN article_analysis aa ON aa.article_id = a.id
                LEFT JOIN article_translations at
                    ON at.article_id = a.id
                    AND at.content_hash = compute_content_hash(a.title, a.content)
                WHERE a.id = ?
                """,
                (article_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT
                    a.id, a.url, a.source,
                    a.published_at, a.crawled_at,
                    a.title AS original_title,
                    a.content AS original_content,
                    a.title AS title,
                    a.content AS content,
                    NULL AS translated_title,
                    NULL AS translated_content,
                    CASE
                    WHEN a.source IN ('naver', 'geeknews') THEN 'not_needed'
                    ELSE 'pending'
                END AS translation_status,
                    COALESCE(aa.summary, a.summary) AS summary,
                    COALESCE(aa.major_category, a.major_category) AS major_category,
                    COALESCE(aa.sub_category, a.sub_category) AS sub_category,
                    COALESCE(aa.tags, a.tags) AS tags
                FROM articles a
                LEFT JOIN article_analysis aa ON aa.article_id = a.id
                WHERE a.id = ?
                """,
                (article_id,),
            ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_dict(row)


@app.get(
    "/categories",
    response_model=list[CategoryCount],
    summary="카테고리 목록 조회",
    description="기사에 사용된 대분류 카테고리와 각 카테고리의 기사 수를 반환합니다.",
    tags=["meta"],
)
def get_categories():
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(aa.major_category, a.major_category) AS major_category,
                   COUNT(*) as count
            FROM articles a
            LEFT JOIN article_analysis aa ON aa.article_id = a.id
            WHERE COALESCE(aa.major_category, a.major_category) IS NOT NULL
            GROUP BY COALESCE(aa.major_category, a.major_category)
            ORDER BY count DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


@app.get(
    "/sources",
    response_model=list[SourceCount],
    summary="출처 목록 조회",
    description="크롤링에 사용된 뉴스 출처와 각 출처의 기사 수를 반환합니다.",
    tags=["meta"],
)
def get_sources():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC"
        ).fetchall()
    return [dict(r) for r in rows]
