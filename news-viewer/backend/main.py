import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = Path(__file__).parent.parent.parent / "crawling-python" / "news.db"

app = FastAPI(title="News Viewer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    d = dict(row)
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    return d


@app.get("/articles")
def get_articles(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    source: str | None = None,
    q: str | None = None,
):
    offset = (page - 1) * size
    conditions = []
    params: list = []

    if category:
        conditions.append("major_category = ?")
        params.append(category)
    if source:
        conditions.append("source = ?")
        params.append(source)
    if q:
        conditions.append("(title LIKE ? OR summary LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with _connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM articles {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM articles {where} ORDER BY crawled_at DESC LIMIT ? OFFSET ?",
            params + [size, offset],
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "size": size,
        "articles": [_row_to_dict(r) for r in rows],
    }


@app.get("/articles/{article_id}")
def get_article(article_id: int):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _row_to_dict(row)


@app.get("/categories")
def get_categories():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT major_category, COUNT(*) as count FROM articles GROUP BY major_category ORDER BY count DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/sources")
def get_sources():
    with _connect() as conn:
        rows = conn.execute(
            "SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC"
        ).fetchall()
    return [dict(r) for r in rows]
