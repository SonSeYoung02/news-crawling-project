import os
import unittest
from unittest.mock import patch


class TestGeminiClientConfig(unittest.TestCase):
    def test_client_uses_v1beta(self):
        import translation.translator as tr
        tr._gemini_client = None
        with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}), \
             patch("google.genai.Client") as mock_client:
            tr.get_gemini_client()
        kwargs = mock_client.call_args.kwargs
        self.assertEqual(kwargs["http_options"]["api_version"], "v1beta")
        tr._gemini_client = None

    def test_default_daily_limit_is_20(self):
        import config
        if "GEMINI_DAILY_LIMIT" not in os.environ:
            self.assertEqual(config.GEMINI_DAILY_LIMIT, 20)


def _job(i, n):
    return {"article_id": i, "title": "t", "content": "a" * (n - 1), "content_hash": f"h{i}"}


class TestBatcher(unittest.TestCase):
    def _ids(self, batches):
        return [[j["article_id"] for j in b] for b in batches]

    def test_groups_by_chars(self):
        from translation.batcher import build_batches
        batches = build_batches([_job(1, 5000), _job(2, 5000), _job(3, 5000)], max_chars=12000, max_articles=10)
        self.assertEqual(self._ids(batches), [[1, 2], [3]])

    def test_groups_by_count(self):
        from translation.batcher import build_batches
        batches = build_batches([_job(i, 100) for i in range(1, 13)], max_chars=12000, max_articles=10)
        self.assertEqual([len(b) for b in batches], [10, 2])

    def test_oversized_article_alone_keeps_order(self):
        from translation.batcher import build_batches
        batches = build_batches([_job(1, 1000), _job(2, 15000), _job(3, 1000)], max_chars=12000, max_articles=10)
        self.assertEqual(self._ids(batches), [[1], [2], [3]])

    def test_empty_queue(self):
        from translation.batcher import build_batches
        self.assertEqual(build_batches([]), [])


if __name__ == "__main__":
    unittest.main()
