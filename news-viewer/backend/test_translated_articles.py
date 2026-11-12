import os
import sqlite3
import tempfile
import unittest

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

os.environ["DB_PATH"] = temp_db_path

from fastapi.testclient import TestClient
import main


def init_test_db(db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS article_translations")
        conn.execute("DROP TABLE IF EXISTS article_analysis")
        conn.execute("DROP TABLE IF EXISTS articles")
        conn.execute("""
            CREATE TABLE articles (
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
        conn.execute("""
            CREATE TABLE article_analysis (
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
        conn.execute("""
            CREATE TABLE article_translations (
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
        conn.commit()


class TestTranslatedArticlesAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_test_db(temp_db_path)
        cls.client = TestClient(main.app)

        # 샘플 데이터 삽입
        with sqlite3.connect(temp_db_path) as conn:
            # 1. 번역 완료된 영문 기사 (devto)
            h1 = main.compute_content_hash('Original English Title', 'Original English Content')
            conn.execute("""
                INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
                VALUES (1, 'https://dev.to/1', 'devto', 'Original English Title', 'Original English Content',
                        '2026-11-12T00:00:00Z', '2026-11-12T01:00:00', 'AI', '["AI"]')
            """)
            conn.execute("""
                INSERT INTO article_translations
                    (article_id, content_hash, translated_title, translated_content, language, status, completed_at, model, created_at, updated_at)
                VALUES (1, ?, '한국어로 번역된 제목', '한국어로 번역된 본문 내용', 'ko', 'completed',
                        '2026-11-12T01:05:00', 'gemini-2.5-flash', '2026-11-12T01:00:00', '2026-11-12T01:05:00')
            """, (h1,))

            # 2. 미번역 영문 기사 (huggingface)
            conn.execute("""
                INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
                VALUES (2, 'https://hf.co/2', 'huggingface', 'Untranslated Title', 'Untranslated Content',
                        '2026-11-12T00:10:00Z', '2026-11-12T01:00:00', 'AI', '["AI"]')
            """)

            # 3. 한국어 소스 기사 (naver)
            conn.execute("""
                INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
                VALUES (3, 'https://naver.com/3', 'naver', '네이버 한국어 뉴스', '한국어 원문 내용',
                        '2026-11-12T00:20:00+09:00', '2026-11-12T01:00:00', 'IT', '["IT"]')
            """)
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except OSError:
            pass

    def test_translated_article_prioritizes_translation(self):
        resp = self.client.get("/articles/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # 번역 완료 기사는 title, content에 번역문이 우선 반영됨
        self.assertEqual(data["title"], "한국어로 번역된 제목")
        self.assertEqual(data["content"], "한국어로 번역된 본문 내용")
        self.assertEqual(data["original_title"], "Original English Title")
        self.assertEqual(data["original_content"], "Original English Content")
        self.assertEqual(data["translated_title"], "한국어로 번역된 제목")
        self.assertEqual(data["translated_content"], "한국어로 번역된 본문 내용")
        self.assertEqual(data["translation_status"], "completed")

    def test_untranslated_article_falls_back_to_original(self):
        resp = self.client.get("/articles/2")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # 미번역 기사는 title, content에 원문 유지 및 translated 필드는 None
        self.assertEqual(data["title"], "Untranslated Title")
        self.assertEqual(data["content"], "Untranslated Content")
        self.assertEqual(data["original_title"], "Untranslated Title")
        self.assertEqual(data["original_content"], "Untranslated Content")
        self.assertIsNone(data["translated_title"])
        self.assertIsNone(data["translated_content"])
        self.assertEqual(data["translation_status"], "pending")

    def test_korean_source_article_status_not_needed(self):
        resp = self.client.get("/articles/3")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["title"], "네이버 한국어 뉴스")
        self.assertEqual(data["content"], "한국어 원문 내용")
        self.assertEqual(data["translation_status"], "not_needed")

    def test_articles_list_contains_translated_fields(self):
        resp = self.client.get("/articles?page=1&size=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["articles"]), 3)

        by_id = {a["id"]: a for a in data["articles"]}
        self.assertEqual(by_id[1]["title"], "한국어로 번역된 제목")
        self.assertEqual(by_id[2]["title"], "Untranslated Title")
        self.assertEqual(by_id[3]["title"], "네이버 한국어 뉴스")


if __name__ == "__main__":
    unittest.main()
