import hashlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient
import main


def compute_content_hash(title: str, content: str) -> str:
    normalized = f"{(title or '').strip()}\n{(content or '').strip()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


class TranslatedArticlesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "news.db"
        self._init_db(with_translations=True)
        self.patch = patch.object(main, "DB_PATH", self.db)
        self.patch.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def _init_db(self, with_translations: bool = True):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("""
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
            c.execute("""
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
            if with_translations:
                c.execute("""
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

    def _add_article(
        self,
        article_id: int,
        title: str = "Original English Title",
        content: str = "Original English Content",
        url: str = "https://example.com/1",
        source: str = "techcrunch",
        category: str = "AI",
        summary: str = "Original summary",
        crawled_at: str = "2026-11-12T01:00:00",
    ):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                """
                INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, summary, major_category, sub_category, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (article_id, url, source, title, content, "2026-11-12T00:00:00Z", crawled_at, summary, category, "Sub", "[\"AI\"]")
            )

    def _add_translation(
        self,
        article_id: int,
        content_hash: str,
        translated_title: str = "한국어 번역 제목",
        translated_content: str = "한국어 번역 본문",
        status: str = "completed",
    ):
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute(
                """
                INSERT INTO article_translations
                    (article_id, content_hash, translated_title, translated_content, language, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'ko', ?, '2026-11-12T01:10:00', '2026-11-12T01:15:00')
                """,
                (article_id, content_hash, translated_title, translated_content, status)
            )

    def test_translated_article_priority_in_list_and_detail(self):
        """번역 완료 기사는 translated_title, translated_content가 기본 title, content로 제공되어야 함."""
        orig_title = "OpenAI Releases New Model"
        orig_content = "The new model shows significant improvements in reasoning."
        trans_title = "OpenAI 새 모델 출시"
        trans_content = "새 모델은 추론 능력에서 상당한 개선을 보여줍니다."
        h = compute_content_hash(orig_title, orig_content)

        self._add_article(1, title=orig_title, content=orig_content)
        self._add_translation(1, h, translated_title=trans_title, translated_content=trans_content, status="completed")

        # 1. 목록 조회
        res = self.client.get("/articles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        item = data["articles"][0]
        self.assertEqual(item["title"], trans_title)
        self.assertEqual(item["content"], trans_content)
        self.assertEqual(item["original_title"], orig_title)
        self.assertEqual(item["original_content"], orig_content)
        self.assertEqual(item["translated_title"], trans_title)
        self.assertEqual(item["translated_content"], trans_content)
        self.assertEqual(item["translation_status"], "completed")

        # 2. 단건 조회
        detail_res = self.client.get("/articles/1")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["title"], trans_title)
        self.assertEqual(detail["content"], trans_content)
        self.assertEqual(detail["original_title"], orig_title)
        self.assertEqual(detail["original_content"], orig_content)
        self.assertEqual(detail["translated_title"], trans_title)
        self.assertEqual(detail["translated_content"], trans_content)
        self.assertEqual(detail["translation_status"], "completed")

    def test_pending_and_failed_translation_fallback(self):
        """번역 미완료(pending, in_progress, failed) 상태 기사는 원문을 반환하고 부분 번역을 노출하지 않아야 함."""
        orig_title = "Pending Article Title"
        orig_content = "Pending Article Content"
        h = compute_content_hash(orig_title, orig_content)

        self._add_article(2, title=orig_title, content=orig_content, url="https://example.com/2")
        self._add_translation(2, h, translated_title="미완료 번역 제목", translated_content="미완료 번역 본문", status="pending")

        res = self.client.get("/articles/2")
        self.assertEqual(res.status_code, 200)
        item = res.json()
        self.assertEqual(item["title"], orig_title)
        self.assertEqual(item["content"], orig_content)
        self.assertEqual(item["original_title"], orig_title)
        self.assertEqual(item["original_content"], orig_content)
        self.assertIsNone(item["translated_title"])
        self.assertIsNone(item["translated_content"])
        self.assertEqual(item["translation_status"], "pending")

    def test_content_change_invalidates_old_translation(self):
        """원문 본문이 변경되어 content_hash가 불일치하면 이전 완료 번역 대신 최신 원문으로 폴백해야 함."""
        old_title = "Version 1 Title"
        old_content = "Version 1 Content"
        old_hash = compute_content_hash(old_title, old_content)

        # 원문은 버전 2로 변경됨
        new_title = "Version 2 Title (Updated)"
        new_content = "Version 2 Content (Updated)"

        self._add_article(3, title=new_title, content=new_content, url="https://example.com/3")
        # 번역 테이블에는 버전 1의 완료 번역만 존재
        self._add_translation(3, old_hash, translated_title="구버전 번역 제목", translated_content="구버전 번역 본문", status="completed")

        res = self.client.get("/articles/3")
        self.assertEqual(res.status_code, 200)
        item = res.json()
        self.assertEqual(item["title"], new_title)
        self.assertEqual(item["content"], new_content)
        self.assertEqual(item["original_title"], new_title)
        self.assertEqual(item["original_content"], new_content)
        self.assertIsNone(item["translated_title"])
        self.assertIsNone(item["translated_content"])
        self.assertEqual(item["translation_status"], "untranslated")

    def test_untranslated_article(self):
        """번역 레코드가 전혀 없는 기사는 원문 및 untranslated 상태를 반환해야 함."""
        self._add_article(4, title="Untranslated Title", content="Untranslated Content", url="https://example.com/4")
        res = self.client.get("/articles/4")
        self.assertEqual(res.status_code, 200)
        item = res.json()
        self.assertEqual(item["title"], "Untranslated Title")
        self.assertEqual(item["content"], "Untranslated Content")
        self.assertEqual(item["original_title"], "Untranslated Title")
        self.assertEqual(item["original_content"], "Untranslated Content")
        self.assertIsNone(item["translated_title"])
        self.assertIsNone(item["translated_content"])
        self.assertEqual(item["translation_status"], "untranslated")

    def test_search_across_multiple_fields(self):
        """검색(q)은 원문 제목, 번역 제목, 원문 본문, 번역 본문, 요약 모두를 대상으로 동작해야 함."""
        # 기사 1: 번역 제목에만 "양자컴퓨팅" 키워드 존재
        t1 = "Quantum Breakthrough"
        c1 = "Scientists achieved supremacy."
        self._add_article(1, title=t1, content=c1, url="https://example.com/q1", summary="summary 1")
        self._add_translation(1, compute_content_hash(t1, c1), translated_title="양자컴퓨팅 돌파구", translated_content="과학자들이 우위를 달성함", status="completed")

        # 기사 2: 원문 본문에만 "superconductor" 키워드 존재
        t2 = "Material Science Update"
        c2 = "New room-temperature superconductor candidate evaluated."
        self._add_article(2, title=t2, content=c2, url="https://example.com/q2", summary="summary 2")
        self._add_translation(2, compute_content_hash(t2, c2), translated_title="재료과학 최신정보", translated_content="새로운 상온 후보 평가됨", status="completed")

        # 기사 3: 번역 본문에만 "생성형인공지능" 키워드 존재
        t3 = "Generative Tech"
        c3 = "Models create impressive code."
        self._add_article(3, title=t3, content=c3, url="https://example.com/q3", summary="summary 3")
        self._add_translation(3, compute_content_hash(t3, c3), translated_title="생성 기술", translated_content="생성형인공지능 모델이 인상적인 코드를 작성함", status="completed")

        # 기사 4: 요약(summary)에만 "특수요약단어" 키워드 존재
        self._add_article(4, title="Plain Title", content="Plain Content", url="https://example.com/q4", summary="특수요약단어 포함")

        # 번역 제목 검색
        res = self.client.get("/articles", params={"q": "양자컴퓨팅"})
        self.assertEqual(res.json()["total"], 1)
        self.assertEqual(res.json()["articles"][0]["id"], 1)

        # 원문 본문 검색
        res = self.client.get("/articles", params={"q": "superconductor"})
        self.assertEqual(res.json()["total"], 1)
        self.assertEqual(res.json()["articles"][0]["id"], 2)

        # 번역 본문 검색
        res = self.client.get("/articles", params={"q": "생성형인공지능"})
        self.assertEqual(res.json()["total"], 1)
        self.assertEqual(res.json()["articles"][0]["id"], 3)

        # 요약 검색 (하위 호환)
        res = self.client.get("/articles", params={"q": "특수요약단어"})
        self.assertEqual(res.json()["total"], 1)
        self.assertEqual(res.json()["articles"][0]["id"], 4)

        # 매칭 없는 검색
        res = self.client.get("/articles", params={"q": "존재하지않는단어XYZ"})
        self.assertEqual(res.json()["total"], 0)

    def test_legacy_db_without_translations_table_fallback(self):
        """article_translations 테이블이 없는 구버전 DB에서도 에러 없이 안전하게 폴백 동작해야 함."""
        # 새 임시 DB에 translation 테이블 없이 초기화
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("DROP TABLE IF EXISTS article_translations")

        self._add_article(10, title="Legacy Title", content="Legacy Content", url="https://example.com/legacy")

        res = self.client.get("/articles")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["articles"][0]["title"], "Legacy Title")
        self.assertEqual(data["articles"][0]["original_title"], "Legacy Title")
        self.assertEqual(data["articles"][0]["translation_status"], "untranslated")

        detail_res = self.client.get("/articles/10")
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["title"], "Legacy Title")
        self.assertEqual(detail_res.json()["translation_status"], "untranslated")

        # 카테고리/출처 조회 정상 확인
        cat_res = self.client.get("/categories")
        self.assertEqual(cat_res.status_code, 200)
        source_res = self.client.get("/sources")
        self.assertEqual(source_res.status_code, 200)

    def test_categories_and_sources_aggregation_unaffected(self):
        """번역 테이블이 존재해도 카테고리 및 출처 집계가 정상 동작해야 함."""
        self._add_article(1, category="AI", source="techcrunch", url="https://example.com/c1")
        self._add_article(2, category="AI", source="arstechnica", url="https://example.com/c2")
        self._add_article(3, category="경제", source="techcrunch", url="https://example.com/c3")

        cats = self.client.get("/categories").json()
        ai_cat = next(c for c in cats if c["major_category"] == "AI")
        self.assertEqual(ai_cat["count"], 2)

        sources = self.client.get("/sources").json()
        tc = next(s for s in sources if s["source"] == "techcrunch")
        self.assertEqual(tc["count"], 2)

    def test_article_not_found_returns_404(self):
        res = self.client.get("/articles/9999")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
