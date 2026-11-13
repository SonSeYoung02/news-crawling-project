import os
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient
import main


def setup_db(db_path: str):
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

        # 기사 1: 영문 기사 + 한국어 번역 완료
        h1 = main.compute_content_hash("Deep Learning Breakthrough", "Transformers are revolutionizing neural networks.")
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
            VALUES (1, 'https://devto.com/dl', 'devto', 'Deep Learning Breakthrough', 'Transformers are revolutionizing neural networks.',
                    '2026-11-12T00:00:00Z', '2026-11-12T01:00:00', 'AI', '["AI"]')
        """)
        conn.execute("""
            INSERT INTO article_translations (article_id, content_hash, translated_title, translated_content, status, created_at, updated_at)
            VALUES (1, ?, '딥러닝의 대도약', '트랜스포머가 인공신경망 분야를 혁신하고 있습니다.', 'completed', '2026-11-12T01:00:00', '2026-11-12T01:05:00')
        """, (h1,))

        # 기사 2: 한국어 기사 (네이버뉴스)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
            VALUES (2, 'https://naver.com/semi', '네이버뉴스', '차세대 반도체 공정 발표', '극자외선 노광 장비 도입이 가속화된다.',
                    '2026-11-12T00:30:00+09:00', '2026-11-12T01:00:00', 'IT', '["반도체"]')
        """)

        # 기사 3: 미번역 영문 기사 (Google News)
        conn.execute("""
            INSERT INTO articles (id, url, source, title, content, published_at, crawled_at, major_category, tags)
            VALUES (3, 'https://news.google.com/fed', 'google_news', 'Federal Reserve Rate Decisions', 'Interest rate cuts expected next quarter.',
                    '2026-11-12T00:15:00Z', '2026-11-12T01:00:00', '경제', '["금리"]')
        """)
        conn.commit()


class TestSearchAndFilters(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        setup_db(self.temp_db_path)
        self.client = TestClient(main.app)

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except OSError:
            pass

    def test_search_by_translated_title(self):
        resp = self.client.get("/articles?q=딥러닝")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["articles"][0]["id"], 1)

    def test_search_by_original_title(self):
        resp = self.client.get("/articles?q=Breakthrough")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["articles"][0]["id"], 1)

    def test_search_by_translated_content(self):
        resp = self.client.get("/articles?q=인공신경망")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["articles"][0]["id"], 1)

    def test_search_by_original_content(self):
        resp = self.client.get("/articles?q=revolutionizing")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["articles"][0]["id"], 1)

    def test_filter_by_category_and_source(self):
        resp = self.client.get("/articles?category=IT")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 1)
        self.assertEqual(resp.json()["articles"][0]["source"], "네이버뉴스")

        resp_src = self.client.get("/articles?source=google_news")
        self.assertEqual(resp_src.status_code, 200)
        self.assertEqual(resp_src.json()["total"], 1)
        self.assertEqual(resp_src.json()["articles"][0]["id"], 3)

    def test_categories_endpoint(self):
        resp = self.client.get("/categories")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        cats = {c["major_category"]: c["count"] for c in data}
        self.assertEqual(cats.get("AI"), 1)
        self.assertEqual(cats.get("IT"), 1)
        self.assertEqual(cats.get("경제"), 1)

    def test_sources_endpoint(self):
        resp = self.client.get("/sources")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        sources = {s["source"]: s["count"] for s in data}
        self.assertEqual(sources.get("devto"), 1)
        self.assertEqual(sources.get("네이버뉴스"), 1)
        self.assertEqual(sources.get("google_news"), 1)


if __name__ == "__main__":
    unittest.main()
