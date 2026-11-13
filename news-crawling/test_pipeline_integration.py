import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import db
import main
from translation import batcher
from translation.batch_translator import DailyQuotaExceeded, PermanentApiError
from translation.rate_limiter import CutoffController, RateLimiter


def fake_gemini(batch, model=None):
    return json.dumps(
        [
            {"id": j["article_id"], "title": "한국어 제목", "content": "한국어 번역 본문 " * 40}
            for j in batch
        ],
        ensure_ascii=False,
    )


def english_articles(n):
    return [
        {
            "url": f"https://example.com/en-{i}",
            "source": "devto",
            "title": f"Title {i}",
            "content": f"Content {i}",
            "published_at": f"2026-11-12T00:0{i}:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        }
        for i in range(n)
    ]


class TestPipelineIntegration(unittest.TestCase):
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

    @patch("translation.batch_translator.call_gemini_batch")
    def test_full_pipeline_run_integration(self, mock_call):
        mock_call.side_effect = fake_gemini

        articles = [
            {
                "url": "https://example.com/int-en",
                "source": "devto",
                "title": "Quantum AI Breakthrough",
                "content": "Quantum computing is revolutionizing AI algorithms.",
                "published_at": "2026-11-12T00:00:00Z",
                "crawled_at": "2026-11-12T01:00:00",
                "major_category": "AI",
                "tags": ["AI"],
            },
            {
                "url": "https://example.com/int-ko",
                "source": "네이버뉴스",
                "title": "국내 반도체 생산 확대",
                "content": "국내 주요 기업들이 투자를 확대한다.",
                "published_at": "2026-11-12T00:10:00+09:00",
                "crawled_at": "2026-11-12T01:00:00",
                "major_category": "IT",
                "tags": ["반도체"],
            },
        ]

        rate_limiter = RateLimiter(daily_limit=10, request_interval=0.01)
        cutoff_controller = CutoffController()

        result = main.run_pipeline(
            sample_articles=articles,
            rate_limiter=rate_limiter,
            cutoff_controller=cutoff_controller,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["saved"], 2)
        self.assertEqual(result["translated"], 1)
        self.assertEqual(result["pending_translation"], 0)
        self.assertEqual(mock_call.call_count, 1)

        # 1. 영어 기사: 번역 레코드 completed 확인
        en_id = db.get_article_id_by_url("https://example.com/int-en")
        en_hash = db.compute_content_hash("Quantum AI Breakthrough", "Quantum computing is revolutionizing AI algorithms.")
        en_trans = db.get_or_create_translation(en_id, en_hash)
        self.assertEqual(en_trans["status"], "completed")
        self.assertEqual(en_trans["translated_title"], "한국어 제목")

        # 2. 한국어 기사: 번역 레코드 없음 확인
        ko_id = db.get_article_id_by_url("https://example.com/int-ko")
        with db._connect() as conn:
            row_trans = conn.execute("SELECT * FROM article_translations WHERE article_id = ?", (ko_id,)).fetchone()
            self.assertIsNone(row_trans)

        # 3. 락 해제 확인
        with db._connect() as conn:
            lock = conn.execute("SELECT * FROM crawl_locks WHERE name = 'nightly_crawl'").fetchone()
            self.assertIsNone(lock)

    @patch("translation.batch_translator.call_gemini_batch")
    def test_pipeline_stops_gracefully_on_cutoff(self, mock_call):
        mock_call.side_effect = fake_gemini

        articles = [
            {
                "url": "https://example.com/cutoff-en-1",
                "source": "devto",
                "title": "Title 1",
                "content": "Content 1",
                "published_at": "2026-11-12T00:00:00Z",
                "crawled_at": "2026-11-12T01:00:00",
            },
            {
                "url": "https://example.com/cutoff-en-2",
                "source": "google_news",
                "title": "Title 2",
                "content": "Content 2",
                "published_at": "2026-11-12T00:05:00Z",
                "crawled_at": "2026-11-12T01:00:00",
            },
        ]

        class ImmediateCutoff:
            def can_request(self, now_dt=None):
                return False

        result = main.run_pipeline(
            sample_articles=articles,
            rate_limiter=RateLimiter(daily_limit=10, request_interval=0.01),
            cutoff_controller=ImmediateCutoff(),
        )

        self.assertEqual(result["status"], "stopped_cutoff")
        self.assertEqual(result["translated"], 0)
        self.assertEqual(result["pending_translation"], 2)
        self.assertEqual(mock_call.call_count, 0)

    @patch("translation.batch_translator.call_gemini_batch")
    def test_pipeline_stops_on_daily_quota_without_failures(self, mock_call):
        mock_call.side_effect = DailyQuotaExceeded("quota")
        result = main.run_pipeline(
            sample_articles=english_articles(3),
            rate_limiter=RateLimiter(daily_limit=10, request_interval=0.01),
            cutoff_controller=CutoffController(),
        )
        self.assertEqual(result["status"], "stopped_daily_quota")
        self.assertEqual(result["failed_translation"], 0)
        self.assertEqual(result["translated"], 0)
        self.assertEqual(result["pending_translation"], 3)
        with db._connect() as conn:
            failed = conn.execute(
                "SELECT COUNT(*) FROM article_translations WHERE status = 'failed'"
            ).fetchone()[0]
        self.assertEqual(failed, 0)

    @patch("translation.batch_translator.call_gemini_batch")
    def test_pipeline_stops_after_two_permanent_errors(self, mock_call):
        mock_call.side_effect = PermanentApiError("bad request")
        original = batcher.build_batches
        with patch(
            "translation.batcher.build_batches",
            side_effect=lambda q, **kw: original(q, max_articles=1),
        ):
            result = main.run_pipeline(
                sample_articles=english_articles(3),
                rate_limiter=RateLimiter(daily_limit=10, request_interval=0.01),
                cutoff_controller=CutoffController(),
            )
        self.assertEqual(mock_call.call_count, 2)
        self.assertEqual(result["status"], "stopped_permanent_error")
        self.assertEqual(result["failed_translation"], 2)
        self.assertEqual(result["pending_translation"], 1)


if __name__ == "__main__":
    unittest.main()
