import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

# 테스트 전 임시 DB 설정
temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

os.environ["DB_PATH"] = temp_db_path

import db


class TestTranslationDB(unittest.TestCase):
    def setUp(self):
        # 각 테스트마다 깨끗한 DB로 초기화
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute("DROP TABLE IF EXISTS crawl_locks")
            conn.execute("DROP TABLE IF EXISTS translation_quota")
            conn.execute("DROP TABLE IF EXISTS translation_chunks")
            conn.execute("DROP TABLE IF EXISTS article_translations")
            conn.execute("DROP TABLE IF EXISTS article_analysis")
            conn.execute("DROP TABLE IF EXISTS articles")
            conn.commit()
        db.init_db()

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except OSError:
            pass

    def test_init_db_creates_all_tables(self):
        with db._connect() as conn:
            tables = [row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        self.assertIn("articles", tables)
        self.assertIn("article_analysis", tables)
        self.assertIn("article_translations", tables)
        self.assertIn("translation_chunks", tables)
        self.assertIn("translation_quota", tables)
        self.assertIn("crawl_locks", tables)

    def test_compute_content_hash(self):
        h1 = db.compute_content_hash("Title 1", "Content 1")
        h2 = db.compute_content_hash("Title 1", "Content 1")
        h3 = db.compute_content_hash("Title 1", "Changed Content")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertEqual(len(h1), 64)

    def test_translation_lifecycle_and_chunks(self):
        # 1. 기사 저장
        article = {
            "url": "https://example.com/ai-1",
            "source": "devto",
            "title": "AI Revolution",
            "content": "Paragraph 1\n\nParagraph 2",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        }
        self.assertTrue(db.save_article(article))
        article_id = db.get_article_id_by_url(article["url"])
        self.assertIsNotNone(article_id)

        content_hash = db.compute_content_hash(article["title"], article["content"])

        # 2. 번역 생성/조회 (pending 상태)
        trans = db.get_or_create_translation(article_id, content_hash)
        self.assertEqual(trans["status"], "pending")
        self.assertEqual(trans["content_hash"], content_hash)

        # 3. 본문 청크 저장 (1/2 번역 완료, 2/2 대기)
        db.save_translation_chunk(
            article_id=article_id,
            content_hash=content_hash,
            chunk_index=0,
            total_chunks=2,
            original_chunk="Paragraph 1",
            translated_chunk="문단 1",
            status="completed",
        )
        db.save_translation_chunk(
            article_id=article_id,
            content_hash=content_hash,
            chunk_index=1,
            total_chunks=2,
            original_chunk="Paragraph 2",
            translated_chunk=None,
            status="pending",
        )

        chunks = db.get_translation_chunks(article_id, content_hash)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["status"], "completed")
        self.assertEqual(chunks[0]["translated_chunk"], "문단 1")
        self.assertEqual(chunks[1]["status"], "pending")
        self.assertIsNone(chunks[1]["translated_chunk"])

        # 4. 청크 2도 번역 완료
        db.save_translation_chunk(
            article_id=article_id,
            content_hash=content_hash,
            chunk_index=1,
            total_chunks=2,
            original_chunk="Paragraph 2",
            translated_chunk="문단 2",
            status="completed",
        )
        chunks = db.get_translation_chunks(article_id, content_hash)
        self.assertTrue(all(c["status"] == "completed" for c in chunks))

        # 5. 전체 번역 완료 처리
        ok = db.complete_article_translation(
            article_id=article_id,
            content_hash=content_hash,
            translated_title="AI 혁명",
            translated_content="문단 1\n\n문단 2",
            model="gemini-2.5-flash",
        )
        self.assertTrue(ok)

        trans_after = db.get_or_create_translation(article_id, content_hash)
        self.assertEqual(trans_after["status"], "completed")
        self.assertEqual(trans_after["translated_title"], "AI 혁명")
        self.assertEqual(trans_after["translated_content"], "문단 1\n\n문단 2")
        self.assertEqual(trans_after["model"], "gemini-2.5-flash")
        self.assertIsNotNone(trans_after["completed_at"])

    def test_daily_quota_persistence(self):
        date_str = "2026-11-12"
        q0 = db.get_daily_quota(date_str)
        self.assertEqual(q0["request_count"], 0)
        self.assertEqual(q0["token_count"], 0)

        # 5회 요청, 1200 토큰 추가
        q1 = db.increment_daily_quota(date_str, requests=5, tokens=1200)
        self.assertEqual(q1["request_count"], 5)
        self.assertEqual(q1["token_count"], 1200)

        # 3회 요청 추가
        q2 = db.increment_daily_quota(date_str, requests=3, tokens=800)
        self.assertEqual(q2["request_count"], 8)
        self.assertEqual(q2["token_count"], 2000)

        # 재조회 시 일치
        q_check = db.get_daily_quota(date_str)
        self.assertEqual(q_check["request_count"], 8)
        self.assertEqual(q_check["token_count"], 2000)

    def test_crawl_lock_mutual_exclusion(self):
        lock_name = "test_nightly_crawl"
        # 1. 락 획득 성공
        self.assertTrue(db.acquire_crawl_lock(name=lock_name, timeout_minutes=60))
        # 2. 이미 획득된 락 재획득 시도 실패
        self.assertFalse(db.acquire_crawl_lock(name=lock_name, timeout_minutes=60))
        # 3. 락 해제
        self.assertTrue(db.release_crawl_lock(name=lock_name))
        # 4. 해제 후 다시 획득 성공
        self.assertTrue(db.acquire_crawl_lock(name=lock_name, timeout_minutes=60))
        db.release_crawl_lock(name=lock_name)

    def test_refresh_article_from_source(self):
        article = {
            "url": "https://example.com/refresh-1",
            "source": "google_news",
            "title": "Original Title",
            "content": "Original Content",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:00:00",
            "major_category": "AI",
            "tags": ["AI"],
        }
        db.save_article(article)

        updated_article = {
            "url": "https://example.com/refresh-1",
            "source": "google_news",
            "title": "Updated Title",
            "content": "Updated Content",
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T02:00:00",
            "major_category": "AI",
            "tags": ["AI", "Tech"],
        }
        refreshed = db.refresh_article_from_source(updated_article)
        self.assertTrue(refreshed)

        fetched = db.get_article_by_url(article["url"])
        self.assertEqual(fetched["title"], "Updated Title")
        self.assertEqual(fetched["content"], "Updated Content")


if __name__ == "__main__":
    unittest.main()
