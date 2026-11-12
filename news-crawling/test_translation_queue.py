import os
import sqlite3
import tempfile
import unittest
from datetime import datetime

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

os.environ["DB_PATH"] = temp_db_path

import db
from translation.queue import get_pending_translation_queue, is_translatable_source


class TestTranslationQueue(unittest.TestCase):
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

    def test_is_translatable_source(self):
        self.assertFalse(is_translatable_source("naver"))
        self.assertFalse(is_translatable_source("geeknews"))
        self.assertTrue(is_translatable_source("devto"))
        self.assertTrue(is_translatable_source("google_news"))
        self.assertTrue(is_translatable_source("reddit_ai"))
        self.assertTrue(is_translatable_source("github_trending"))
        self.assertTrue(is_translatable_source("huggingface"))
        self.assertTrue(is_translatable_source("arxiv"))

    def test_queue_ordering_and_filtering(self):
        # 1. 기사 4건 삽입
        # 기사 1: 이전 미번역 기사 (발행일: 2026-11-12T00:30:00Z)
        db.save_article({
            "url": "https://example.com/old-en",
            "source": "devto",
            "title": "Old English Article",
            "content": "Content of old article",
            "published_at": "2026-11-12T00:30:00Z",
            "crawled_at": "2026-11-11T01:00:00",
        })
        old_id = db.get_article_id_by_url("https://example.com/old-en")

        # 기사 2: 한국어 기사 (번역 불필요)
        db.save_article({
            "url": "https://example.com/ko",
            "source": "geeknews",
            "title": "긱뉴스 한국어 기사",
            "content": "한국어 내용",
            "published_at": "2026-11-12T00:40:00+09:00",
            "crawled_at": "2026-11-12T01:00:00",
        })
        ko_id = db.get_article_id_by_url("https://example.com/ko")

        # 기사 3: 신규 기사 A (발행일: 2026-11-12T00:10:00Z)
        db.save_article({
            "url": "https://example.com/new-en-1",
            "source": "github_trending",
            "title": "New Article A",
            "content": "Content A",
            "published_at": "2026-11-12T00:10:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        })
        new_a_id = db.get_article_id_by_url("https://example.com/new-en-1")

        # 기사 4: 신규 기사 B (발행일: 2026-11-12T00:20:00Z - A보다 최신)
        db.save_article({
            "url": "https://example.com/new-en-2",
            "source": "huggingface",
            "title": "New Article B",
            "content": "Content B",
            "published_at": "2026-11-12T00:20:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        })
        new_b_id = db.get_article_id_by_url("https://example.com/new-en-2")

        # 기사 5: 이미 번역 완료된 기사
        db.save_article({
            "url": "https://example.com/completed-en",
            "source": "arxiv",
            "title": "Completed Article",
            "content": "Content Completed",
            "published_at": "2026-11-12T00:25:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        })
        comp_id = db.get_article_id_by_url("https://example.com/completed-en")
        comp_hash = db.compute_content_hash("Completed Article", "Content Completed")
        db.get_or_create_translation(comp_id, comp_hash)
        db.complete_article_translation(comp_id, comp_hash, "완료된 제목", "완료된 본문", "gemini-2.5-flash")

        # 이번 실행의 신규 ID 세트: new_a_id, new_b_id, comp_id, ko_id
        new_ids = {new_a_id, new_b_id, comp_id, ko_id}

        queue = get_pending_translation_queue(new_ids)

        # 검증:
        # 1. 한국어 기사와 완료된 기사는 대기열에서 제외
        queued_ids = [job["article_id"] for job in queue]
        self.assertNotIn(ko_id, queued_ids)
        self.assertNotIn(comp_id, queued_ids)

        # 2. 우선순위: 신규 기사(new_b_id, new_a_id)가 이전 미번역 기사(old_id)보다 앞서야 함
        # 신규 기사 중에서는 최신 발행일인 new_b_id가 new_a_id보다 앞서야 함
        expected_ids = [new_b_id, new_a_id, old_id]
        self.assertEqual(queued_ids, expected_ids)

        # 속성 확인
        self.assertTrue(queue[0]["is_new_in_run"])
        self.assertTrue(queue[1]["is_new_in_run"])
        self.assertFalse(queue[2]["is_new_in_run"])


if __name__ == "__main__":
    unittest.main()
