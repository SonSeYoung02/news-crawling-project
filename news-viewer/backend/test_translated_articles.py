import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
import main

FIXED_NOW = datetime(2026, 11, 12, 12, 0, 0, tzinfo=timezone.utc)


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

        # 3. 한국어 소스 기사 (실제 크롤러 출처값: 네이버뉴스)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
            VALUES (3, 'https://news.naver.com/3', '네이버뉴스', '네이버 한국어 뉴스', '한국어 원문 내용',
                    '2026-11-12T00:20:00+09:00', '2026-11-12T01:00:00', 'IT', '["IT"]')
        """)
        conn.commit()


class TestTranslatedArticlesAPI(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        init_test_db(self.temp_db_path)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_translated_article_prioritizes_translation(self):
        resp = self.client.get("/articles/1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

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

        self.assertEqual(data["source"], "네이버뉴스")
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
        self.assertEqual(by_id[1]["translation_status"], "completed")
        self.assertEqual(by_id[2]["title"], "Untranslated Title")
        self.assertEqual(by_id[2]["translation_status"], "pending")
        self.assertEqual(by_id[3]["title"], "네이버 한국어 뉴스")
        self.assertEqual(by_id[3]["translation_status"], "not_needed")


def init_regression_db(db_path: str, with_translations_table: bool):
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

        if with_translations_table:
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

        # 1. 영문 기사 (devto, AI) - 번역 완료
        h1 = main.compute_content_hash('AI Breakthrough Title', 'AI Breakthrough Content')
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (1, 'https://dev.to/ai-1', 'devto', 'AI Breakthrough Title', 'AI Breakthrough Content',
                    '2026-11-12T10:00:00Z', '2026-11-12T11:00:00', 'AI', 'LLM', '["AI"]')
        """)
        if with_translations_table:
            conn.execute("""
                INSERT INTO article_translations
                    (article_id, content_hash, translated_title, translated_content, language, status, completed_at, model, created_at, updated_at)
                VALUES (1, ?, '인공지능 대도약 제목', '인공지능 대도약 내용', 'ko', 'completed',
                        '2026-11-12T11:05:00', 'gemini-2.5-flash', '2026-11-12T11:00:00', '2026-11-12T11:05:00')
            """, (h1,))

        # 2. 영문 미번역 기사 (huggingface, AI)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (2, 'https://hf.co/ai-2', 'huggingface', 'Open Source Model', 'Weights released.',
                    '2026-11-12T09:00:00Z', '2026-11-12T10:00:00', 'AI', 'Vision', '["AI"]')
        """)

        # 3. 한국어 출처 기사 (네이버뉴스, AI)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (3, 'https://news.naver.com/ai-3', '네이버뉴스', '네이버 생성 AI 공개', '네이버 하이퍼클로바X 세부 내용',
                    '2026-11-12T08:00:00Z', '2026-11-12T09:00:00', 'AI', 'Search', '["AI"]')
        """)

        # 4. 한국어 출처 기사 (GeekNews, AI)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (4, 'https://news.hada.io/ai-4', 'GeekNews', '긱뉴스 AI 오픈소스 소식', '깃허브 트렌딩 AI 도구 소개',
                    '2026-11-12T07:00:00Z', '2026-11-12T08:00:00', 'AI', 'Tool', '["AI"]')
        """)

        # 5. 레거시 한국어 기사 (naver, IT)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (5, 'https://naver.com/it-5', 'naver', '레거시 네이버 뉴스', 'IT 동향 내용',
                    '2026-11-12T06:00:00Z', '2026-11-12T07:00:00', 'IT', 'Cloud', '["IT"]')
        """)

        # 6. 레거시 한국어 기사 (geeknews, IT)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, sub_category, tags)
            VALUES (6, 'https://geeknews.com/it-6', 'geeknews', '레거시 긱뉴스 뉴스', '개발자 팁 내용',
                    '2026-11-12T05:00:00Z', '2026-11-12T06:00:00', 'IT', 'Coding', '["IT"]')
        """)
        conn.commit()


class TestKoreanSourceRegressionWithTranslationsTable(unittest.TestCase):
    """번역 테이블(article_translations)이 존재하는 DB 환경에서의 회귀 테스트"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        init_regression_db(self.temp_db_path, with_translations_table=True)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_articles_list_translation_status(self):
        resp = self.client.get("/articles?page=1&size=10")
        self.assertEqual(resp.status_code, 200)
        articles = {a["id"]: a for a in resp.json()["articles"]}

        # 번역 완료 영문 기사: completed
        self.assertEqual(articles[1]["source"], "devto")
        self.assertEqual(articles[1]["translation_status"], "completed")

        # 미번역 영문 기사: pending
        self.assertEqual(articles[2]["source"], "huggingface")
        self.assertEqual(articles[2]["translation_status"], "pending")

        # 한국어 출처 (네이버뉴스, GeekNews): not_needed
        self.assertEqual(articles[3]["source"], "네이버뉴스")
        self.assertEqual(articles[3]["translation_status"], "not_needed")

        self.assertEqual(articles[4]["source"], "GeekNews")
        self.assertEqual(articles[4]["translation_status"], "not_needed")

        # 레거시 한국어 출처 (naver, geeknews): not_needed
        self.assertEqual(articles[5]["source"], "naver")
        self.assertEqual(articles[5]["translation_status"], "not_needed")

        self.assertEqual(articles[6]["source"], "geeknews")
        self.assertEqual(articles[6]["translation_status"], "not_needed")

    def test_article_detail_translation_status(self):
        # 영문 미번역 기사: pending
        resp2 = self.client.get("/articles/2")
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["translation_status"], "pending")

        # 네이버뉴스: not_needed
        resp3 = self.client.get("/articles/3")
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.json()["translation_status"], "not_needed")

        # GeekNews: not_needed
        resp4 = self.client.get("/articles/4")
        self.assertEqual(resp4.status_code, 200)
        self.assertEqual(resp4.json()["translation_status"], "not_needed")

        # 레거시 naver: not_needed
        resp5 = self.client.get("/articles/5")
        self.assertEqual(resp5.status_code, 200)
        self.assertEqual(resp5.json()["translation_status"], "not_needed")

        # 레거시 geeknews: not_needed
        resp6 = self.client.get("/articles/6")
        self.assertEqual(resp6.status_code, 200)
        self.assertEqual(resp6.json()["translation_status"], "not_needed")

    def test_briefing_translation_status(self):
        with patch.object(main, "_utc_now", return_value=FIXED_NOW):
            resp = self.client.get("/briefing")
        self.assertEqual(resp.status_code, 200)
        briefing_articles = {a["id"]: a for a in resp.json()["articles"]}

        self.assertIn(1, briefing_articles)
        self.assertEqual(briefing_articles[1]["translation_status"], "completed")

        self.assertIn(2, briefing_articles)
        self.assertEqual(briefing_articles[2]["translation_status"], "pending")

        self.assertIn(3, briefing_articles)
        self.assertEqual(briefing_articles[3]["translation_status"], "not_needed")

        self.assertIn(4, briefing_articles)
        self.assertEqual(briefing_articles[4]["translation_status"], "not_needed")


class TestKoreanSourceRegressionWithoutTranslationsTable(unittest.TestCase):
    """번역 테이블(article_translations)이 없는 DB 환경에서의 회귀 테스트"""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        init_regression_db(self.temp_db_path, with_translations_table=False)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_articles_list_translation_status_without_table(self):
        resp = self.client.get("/articles?page=1&size=10")
        self.assertEqual(resp.status_code, 200)
        articles = {a["id"]: a for a in resp.json()["articles"]}

        # 번역 테이블이 없으므로 영문 기사들은 모두 pending
        self.assertEqual(articles[1]["source"], "devto")
        self.assertEqual(articles[1]["translation_status"], "pending")
        self.assertIsNone(articles[1]["translated_title"])

        self.assertEqual(articles[2]["source"], "huggingface")
        self.assertEqual(articles[2]["translation_status"], "pending")

        # 한국어 출처 (네이버뉴스, GeekNews)는 not_needed
        self.assertEqual(articles[3]["source"], "네이버뉴스")
        self.assertEqual(articles[3]["translation_status"], "not_needed")

        self.assertEqual(articles[4]["source"], "GeekNews")
        self.assertEqual(articles[4]["translation_status"], "not_needed")

        # 레거시 한국어 출처도 not_needed
        self.assertEqual(articles[5]["source"], "naver")
        self.assertEqual(articles[5]["translation_status"], "not_needed")

        self.assertEqual(articles[6]["source"], "geeknews")
        self.assertEqual(articles[6]["translation_status"], "not_needed")

    def test_article_detail_translation_status_without_table(self):
        # 영문 기사: pending
        resp1 = self.client.get("/articles/1")
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.json()["translation_status"], "pending")

        # 네이버뉴스: not_needed
        resp3 = self.client.get("/articles/3")
        self.assertEqual(resp3.status_code, 200)
        self.assertEqual(resp3.json()["translation_status"], "not_needed")

        # GeekNews: not_needed
        resp4 = self.client.get("/articles/4")
        self.assertEqual(resp4.status_code, 200)
        self.assertEqual(resp4.json()["translation_status"], "not_needed")

        # 레거시 출처: not_needed
        resp5 = self.client.get("/articles/5")
        self.assertEqual(resp5.status_code, 200)
        self.assertEqual(resp5.json()["translation_status"], "not_needed")

    def test_briefing_translation_status_without_table(self):
        with patch.object(main, "_utc_now", return_value=FIXED_NOW):
            resp = self.client.get("/briefing")
        self.assertEqual(resp.status_code, 200)
        briefing_articles = {a["id"]: a for a in resp.json()["articles"]}

        # 영문 기사는 pending
        self.assertIn(1, briefing_articles)
        self.assertEqual(briefing_articles[1]["translation_status"], "pending")

        self.assertIn(2, briefing_articles)
        self.assertEqual(briefing_articles[2]["translation_status"], "pending")

        # 한국어 출처는 not_needed
        self.assertIn(3, briefing_articles)
        self.assertEqual(briefing_articles[3]["translation_status"], "not_needed")

        self.assertIn(4, briefing_articles)
        self.assertEqual(briefing_articles[4]["translation_status"], "not_needed")


if __name__ == "__main__":
    unittest.main()
