import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import db
from translation.chunker import chunk_text
from translation.translator import translate_article_job


class DummyRateLimiter:
    def __init__(self, allow=True):
        self.allow = allow

    def can_consume(self, requests=1):
        return self.allow

    def wait_and_consume(self, tokens=100, requests=1):
        return self.allow


class DummyCutoffController:
    def __init__(self, can_request=True):
        self._can_request = can_request

    def can_request(self, now_dt=None):
        return self._can_request


class TestChunkerAndTranslator(unittest.TestCase):
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

    def test_chunk_text_small_and_large(self):
        short = "This is a short article."
        chunks = chunk_text(short, max_chars=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short)

        p1 = "Paragraph 1: " + ("A" * 80)
        p2 = "Paragraph 2: " + ("B" * 80)
        p3 = "Paragraph 3: " + ("C" * 80)
        long_text = f"{p1}\n\n{p2}\n\n{p3}"
        chunks_long = chunk_text(long_text, max_chars=120)
        self.assertEqual(len(chunks_long), 3)
        self.assertEqual(chunks_long[0], p1)
        self.assertEqual(chunks_long[1], p2)
        self.assertEqual(chunks_long[2], p3)

    @patch("translation.translator._call_gemini_api")
    def test_translate_article_job_with_resume(self, mock_gemini):
        mock_gemini.side_effect = lambda prompt, **kwargs: f"[번역] {prompt[:20]}"

        p1 = "First chunk of content. " + ("X" * 60)
        p2 = "Second chunk of content. " + ("Y" * 60)
        content = f"{p1}\n\n{p2}"

        article = {
            "url": "https://example.com/chunk-test",
            "source": "devto",
            "title": "Chunked Title",
            "content": content,
            "published_at": "2026-11-12T00:00:00Z",
            "crawled_at": "2026-11-12T01:00:00",
        }
        db.save_article(article)
        aid = db.get_article_id_by_url(article["url"])
        content_hash = db.compute_content_hash(article["title"], content)

        job = {
            "article_id": aid,
            "url": article["url"],
            "title": article["title"],
            "content": content,
            "content_hash": content_hash,
            "source": "devto",
        }

        rate_limiter = DummyRateLimiter(allow=True)
        call_count = [0]

        class SteppedCutoff:
            def can_request(self, now_dt=None):
                call_count[0] += 1
                return call_count[0] <= 2

        ok1 = translate_article_job(
            job=job,
            rate_limiter=rate_limiter,
            cutoff_controller=SteppedCutoff(),
            max_chars=90,
        )
        self.assertFalse(ok1)

        trans_mid = db.get_or_create_translation(aid, content_hash)
        self.assertEqual(trans_mid["status"], "pending")
        chunks_mid = db.get_translation_chunks(aid, content_hash)
        self.assertGreaterEqual(len(chunks_mid), 1)
        self.assertEqual(chunks_mid[0]["status"], "completed")

        calls_phase1 = mock_gemini.call_count

        ok2 = translate_article_job(
            job=job,
            rate_limiter=DummyRateLimiter(allow=True),
            cutoff_controller=DummyCutoffController(can_request=True),
            max_chars=90,
        )
        self.assertTrue(ok2)

        calls_phase2 = mock_gemini.call_count - calls_phase1
        self.assertEqual(calls_phase2, 1)

        trans_final = db.get_or_create_translation(aid, content_hash)
        self.assertEqual(trans_final["status"], "completed")
        self.assertIsNotNone(trans_final["translated_title"])
        self.assertIsNotNone(trans_final["translated_content"])
        self.assertIn("[번역]", trans_final["translated_content"])


if __name__ == "__main__":
    unittest.main()
