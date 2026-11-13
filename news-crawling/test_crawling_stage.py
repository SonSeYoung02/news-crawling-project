import os
import sqlite3
import sys
import tempfile
import unittest

import db
import main


class TestCrawlingStage(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        os.environ["DB_PATH"] = self.temp_db_path
        db.init_db()

    def tearDown(self):
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
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
                "source": "네이버뉴스",
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
        saved, refreshed, failed, new_ids = main.crawl_and_save_articles(sample)
        self.assertEqual(saved, 1)
        # 요약·분류용 llm 모듈은 제거되었으며, 수집 단계에서 다시 불러오지 않아야 한다.
        self.assertNotIn("llm", sys.modules)
        self.assertNotIn("llm.analyzer", sys.modules)


if __name__ == "__main__":
    unittest.main()
