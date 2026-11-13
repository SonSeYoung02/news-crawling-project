"""articles.content에 남은 HTML 태그 문자열을 일반 텍스트로 정리하는 1회성 스크립트 (#58).

기본은 dry-run이며 `--apply`를 지정해야만 DB에 반영한다. 반영 전에는
`news.db.bak-YYYYMMDDHHMMSS` 백업 파일을 만든다. article_analysis는 건드리지 않는다.

사용 예 (news-crawling 디렉터리에서):
    python scripts/clean_html_content.py
    python scripts/clean_html_content.py --db path/to/news.db --apply
"""

import argparse
import logging
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH  # noqa: E402
from crawlers._html_text import html_to_text, looks_like_html  # noqa: E402

logger = logging.getLogger("clean_html_content")

# 태그 흔적 후보를 SQL에서 1차로 거르고, looks_like_html로 최종 판정한다.
_TAG_MARKERS = ("<div", "<li", "<p>", "<p ", "<ul", "<ol", "<br", "<strong", "<a ", "<h1", "<h2", "<h3", "<em>", "<code>", "<hr")
_PREVIEW_CHARS = 200
# 피드 HTML을 이중 escape로 저장하던 크롤러(#58)만 기본 대상으로 한다.
# dev.to 등은 markdown 본문에 HTML 예시가 섞여 있어 변환하면 원문이 손상된다.
_DEFAULT_SOURCES = ("GeekNews", "Reddit AI", "Hugging Face")


def _build_where(column: str) -> tuple[str, list[str]]:
    clause = " OR ".join(f"instr(lower({column}), ?) > 0" for _ in _TAG_MARKERS)
    return f"({clause})", list(_TAG_MARKERS)


def _find_article_targets(conn: sqlite3.Connection, sources: list[str]) -> list[sqlite3.Row]:
    where, params = _build_where("content")
    source_placeholders = ", ".join("?" for _ in sources)
    return conn.execute(
        f"SELECT id, source, title, content FROM articles "
        f"WHERE source IN ({source_placeholders}) AND {where} ORDER BY id",
        [*sources, *params],
    ).fetchall()


def _count_translation_targets(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("article_translations",),
    ).fetchone()
    if not exists:
        return []
    where, params = _build_where("translated_content")
    return conn.execute(
        f"SELECT id, article_id, status FROM article_translations "
        f"WHERE translated_content IS NOT NULL AND {where} ORDER BY id",
        params,
    ).fetchall()


def _preview(text: str) -> str:
    snippet = text[:_PREVIEW_CHARS]
    suffix = "..." if len(text) > _PREVIEW_CHARS else ""
    return snippet.replace("\n", "\\n") + suffix


def _backup(db_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = db_path.with_name(f"{db_path.name}.bak-{stamp}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def run(db_path: Path, apply: bool, sources: list[str]) -> int:
    if not db_path.exists():
        logger.error("DB 파일이 없습니다: %s", db_path)
        return 1

    uri = f"file:{db_path.as_posix()}" + ("" if apply else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = _find_article_targets(conn, sources)
        updates: list[tuple[str, int]] = []
        per_source: dict[str, int] = {}
        for row in rows:
            if not looks_like_html(row["content"]):
                continue
            cleaned = html_to_text(row["content"]) or row["title"]
            if cleaned == row["content"]:
                continue
            updates.append((cleaned[:8000], row["id"]))
            per_source[row["source"]] = per_source.get(row["source"], 0) + 1
            print(f"--- article id={row['id']} source={row['source']} title={row['title'][:60]}")
            print(f"  [전] {_preview(row['content'])}")
            print(f"  [후] {_preview(cleaned)}")

        print()
        print(f"대상 출처: {', '.join(sources)}")
        print(f"정리 대상 articles: {len(updates)}건")
        for source, count in sorted(per_source.items()):
            print(f"  - {source}: {count}건")

        translation_rows = _count_translation_targets(conn)
        print(f"태그가 남은 article_translations.translated_content: {len(translation_rows)}건 (이 스크립트는 수정하지 않음)")
        for row in translation_rows:
            print(f"  - translation id={row['id']} article_id={row['article_id']} status={row['status']}")

        if not apply:
            print("dry-run 모드입니다. 반영하려면 --apply 옵션을 지정하세요.")
            return 0
        if not updates:
            print("반영할 변경이 없습니다.")
            return 0

        conn.close()
        backup_path = _backup(db_path)
        print(f"백업 생성: {backup_path}")
        conn = sqlite3.connect(db_path)
        with conn:
            conn.executemany("UPDATE articles SET content = ? WHERE id = ?", updates)
        print(f"반영 완료: {len(updates)}건")
        return 0
    finally:
        conn.close()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="articles.content에 남은 HTML 태그를 일반 텍스트로 정리한다.")
    parser.add_argument("--db", type=Path, default=Path(DB_PATH), help="대상 SQLite DB 경로 (기본: config.DB_PATH)")
    parser.add_argument("--apply", action="store_true", help="실제로 DB에 반영한다 (기본은 dry-run)")
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help=f"정리할 출처 (여러 번 지정 가능, 기본: {', '.join(_DEFAULT_SOURCES)})",
    )
    args = parser.parse_args()
    return run(args.db.resolve(), args.apply, args.sources or list(_DEFAULT_SOURCES))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
