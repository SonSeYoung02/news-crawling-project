import json
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


def _ko(n):
    return "엔비디아가 실적을 발표했다. " * n


def _src_batch():
    return [
        {"article_id": 1, "title": "AI chips", "content": "Nvidia reports " * 30},
        {"article_id": 2, "title": "GPU news", "content": "Nvidia reports " * 30},
    ]


class _FakeApiError(Exception):
    def __init__(self, code, message, details):
        super().__init__(f"{code} {message}")
        self.code = code
        self.message = message
        self.details = details


class TestBatchParsing(unittest.TestCase):
    def _raw(self, items):
        return json.dumps(items, ensure_ascii=False)

    def test_parse_valid_response(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw([
            {"id": 1, "title": "AI 칩", "content": _ko(20)},
            {"id": 2, "title": "GPU 소식", "content": _ko(20)},
        ])
        self.assertEqual(set(parse_batch_response(raw, _src_batch())), {1, 2})

    def test_parse_accepts_string_ids(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw([{"id": "1", "title": "AI 칩", "content": _ko(20)}])
        self.assertEqual(set(parse_batch_response(raw, _src_batch())), {1})

    def test_parse_strips_code_fence(self):
        from translation.batch_translator import parse_batch_response
        raw = "```json\n" + self._raw([{"id": 1, "title": "AI 칩", "content": _ko(20)}]) + "\n```"
        self.assertEqual(set(parse_batch_response(raw, _src_batch())), {1})

    def test_parse_accepts_wrapped_list(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw({"articles": [{"id": 1, "title": "AI 칩", "content": _ko(20)}]})
        self.assertEqual(set(parse_batch_response(raw, _src_batch())), {1})

    def test_parse_non_list_raises(self):
        from translation.batch_translator import parse_batch_response, BatchParseError
        with self.assertRaises(BatchParseError):
            parse_batch_response('{"id": 1}', _src_batch())

    def test_parse_drops_unknown_duplicate_and_non_korean(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw([
            {"id": 99, "title": "없는 기사", "content": _ko(20)},
            {"id": 1, "title": "AI 칩", "content": _ko(20)},
            {"id": 1, "title": "AI 칩 2", "content": _ko(20)},
            {"id": 2, "title": "GPU news", "content": "Nvidia reports " * 30},
        ])
        self.assertEqual(parse_batch_response(raw, _src_batch()), {})

    def test_parse_drops_suspected_summary(self):
        from translation.batch_translator import parse_batch_response
        batch = [{"article_id": 1, "title": "t", "content": "x" * 1000}]
        raw = self._raw([{"id": 1, "title": "요약", "content": "가" * 200}])
        self.assertEqual(parse_batch_response(raw, batch), {})

    def test_validate_allows_empty_content_when_source_empty(self):
        from translation.batch_translator import parse_batch_response
        batch = [{"article_id": 1, "title": "AI chips", "content": ""}]
        raw = self._raw([{"id": 1, "title": "AI 칩", "content": ""}])
        self.assertEqual(parse_batch_response(raw, batch), {1: {"title": "AI 칩", "content": ""}})

    def test_parse_drops_empty_content_when_source_nonempty(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw([{"id": 1, "title": "AI 칩", "content": ""}])
        self.assertEqual(parse_batch_response(raw, _src_batch()), {})

    def test_parse_skips_malformed_items(self):
        from translation.batch_translator import parse_batch_response
        raw = self._raw(["문자열", {"title": "id 없음"}, {"id": 1, "title": "AI 칩", "content": _ko(20)}])
        self.assertEqual(set(parse_batch_response(raw, _src_batch())), {1})

    def test_parse_broken_json_raises(self):
        from translation.batch_translator import parse_batch_response, BatchParseError
        with self.assertRaises(BatchParseError):
            parse_batch_response('[{"id": 1, "title": "AI', _src_batch())

    def test_call_gemini_batch_request_shape(self):
        from unittest import mock
        from translation import batch_translator as bt
        client = mock.MagicMock()
        client.models.generate_content.return_value.text = "[]"
        with mock.patch.object(bt.translator, "get_gemini_client", return_value=client):
            out = bt.call_gemini_batch(_src_batch())
        self.assertEqual(out, "[]")
        kwargs = client.models.generate_content.call_args.kwargs
        config = kwargs["config"]
        self.assertEqual(config.response_mime_type, "application/json")
        self.assertEqual(config.thinking_config.thinking_budget, 0)
        expected = json.dumps(
            [{"id": 1, "title": "AI chips", "content": "Nvidia reports " * 30},
             {"id": 2, "title": "GPU news", "content": "Nvidia reports " * 30}],
            ensure_ascii=False)
        self.assertIn(expected, kwargs["contents"])

    def test_call_gemini_batch_classifies_errors(self):
        from unittest import mock
        from translation import batch_translator as bt
        client = mock.MagicMock()
        client.models.generate_content.side_effect = _FakeApiError(400, "bad", {})
        with mock.patch.object(bt.translator, "get_gemini_client", return_value=client):
            with self.assertRaises(bt.PermanentApiError):
                bt.call_gemini_batch(_src_batch())


class TestErrorClassification(unittest.TestCase):
    def test_classify_daily_quota(self):
        from translation.batch_translator import classify_api_error, DailyQuotaExceeded
        details = {"error": {"code": 429, "details": [
            {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "70490s"},
        ]}}
        self.assertIsInstance(classify_api_error(_FakeApiError(429, "Quota exceeded", details)), DailyQuotaExceeded)
        e2 = _FakeApiError(429, "GenerateRequestsPerDayPerProjectPerModel-FreeTier", None)
        self.assertIsInstance(classify_api_error(e2), DailyQuotaExceeded)

    def test_classify_minute_limit(self):
        from translation.batch_translator import classify_api_error, MinuteRateLimited
        details = {"error": {"details": [
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}]}}
        r = classify_api_error(_FakeApiError(429, "slow down", details))
        self.assertIsInstance(r, MinuteRateLimited)
        self.assertEqual(r.retry_seconds, 37)

    def test_classify_minute_limit_fractional_and_default(self):
        from translation.batch_translator import classify_api_error
        details = {"error": {"details": [{"retryDelay": "37.5s"}]}}
        self.assertEqual(classify_api_error(_FakeApiError(429, "x", details)).retry_seconds, 37.5)
        self.assertEqual(classify_api_error(_FakeApiError(429, "x", None)).retry_seconds, 60)

    def test_classify_bad_request(self):
        from translation.batch_translator import classify_api_error, PermanentApiError
        for code in (400, 403, 404):
            self.assertIsInstance(classify_api_error(_FakeApiError(code, "bad", {})), PermanentApiError)

    def test_classify_server_and_network_errors(self):
        from translation.batch_translator import classify_api_error, MinuteRateLimited
        r = classify_api_error(_FakeApiError(503, "unavailable", {}))
        self.assertIsInstance(r, MinuteRateLimited)
        self.assertEqual(r.retry_seconds, 10)
        r = classify_api_error(ConnectionError("net"))
        self.assertIsInstance(r, MinuteRateLimited)
        self.assertEqual(r.retry_seconds, 10)


if __name__ == "__main__":
    unittest.main()
