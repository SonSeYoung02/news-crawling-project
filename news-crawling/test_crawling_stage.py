import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

os.environ["DB_PATH"] = temp_db_path

import db
import main


class TestCrawlingStage(unittest.TestCase):
    def setUp(self):
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS crawl_locks")
            conn.execute("DROP TABLE IF EXISTS translation_quota")
            conn.execute("DROP TABLE IF EXISTS translation_chunks")
            conn.execute("DROP TABLE IF EXISTS article_translations")
            conn.execute("DROP TABLE IF EXISTS article_analysis")
            conn.execute("DROP TABLE IF EXISTS articles")
            conn.commit()
        db.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except OSError:
            pass

    def test_crawl_and_save_new_articles(self):
        sample_articles = [
            {
                "url": "https://example.com/en-1",
                "source": "devto",
                "title": "Getting started with LLMs",
                "content": "LLMs are changing everything.",
                "published_at": "2026-11-12T00:00:00Z",
                "crawled_at": "2026-11-12T01:00:00",
                "major_category": "AI",
                "tags": ["AI", "LLM"],
            },
            {
                "url": "https://example.com/ko-1",
                "source": "naver",
                "title": "인공지능 생태계 확장",
                "content": "국내 AI 생태계가 빠르게 확장 중이다.",
                "published_at": "2026-11-12T00:30:00+09:00",
                "crawled_at": "2026-11-12T01:00:00",
                "major_category": "AI",
                "tags": ["AI"],
            },
        ]
        saved, refreshed, failed, new_ids = main.crawl_and_save_articles(sample_articles)
        self.assertEqual(saved, 2)
        self.assertEqual(refreshed, 0)
        self.assertEqual(failed, 0)
        self.assertEqual(len(new_ids), 2)

        # DB 원문 저장 검증
        row_en = db.get_article_by_url("https://example.com/en-1")
        self.assertIsNotNone(row_en)
        self.assertEqual(row_en["title"], "Getting started with LLMs")
        self.assertEqual(row_en["content"], "LLMs are changing everything.")

        row_ko = db.get_article_by_url("https://example.com/ko-1")
        self.assertIsNotNone(row_ko)
        self.assertEqual(row_ko["title"], "인공지능 생태계 확장")

    def test_duplicate_article_refresh_preserves_count(self):
        initial_article = {
            "url": "https://example.com/dup-1",
            "source": "google_news",
            "title": "Old Headline",
            "content": "Old Content",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        }
        main.crawl_and_save_articles([initial_article])

        updated_article = {
            "url": "https://example.com/dup-1",
            "source": "google_news",
            "title": "Breaking: New Headline",
            "content": "Full detailed content updated.",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:30:00",
        }
        saved, refreshed, failed, new_ids = main.crawl_and_save_articles([updated_article])
        self.assertEqual(saved, 0)
        self.assertEqual(refreshed, 1)
        self.assertEqual(failed, 0)
        self.assertEqual(len(new_ids), 0)

        row = db.get_article_by_url("https://example.com/dup-1")
        self.assertEqual(row["title"], "Breaking: New Headline")
        self.assertEqual(row["content"], "Full detailed content updated.")

    def test_no_summarize_or_classify_during_crawling(self):
        sample = [{
            "url": "https://example.com/no-llm",
            "source": "huggingface",
            "title": "HF Daily Papers",
            "content": "New paper about transformers.",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        }]
        # llm.analyzer 모듈이 import되거나 호출되지 않는지 검증
        with patch("llm.analyzer.summarize", create=True) as mock_sum, \
             patch("llm.analyzer.classify", create=True) as mock_cls:
            saved, refreshed, failed, new_ids = main.crawl_and_save_articles(sample)
            self.assertEqual(saved, 1)
            mock_sum.assert_not_called()
            mock_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
