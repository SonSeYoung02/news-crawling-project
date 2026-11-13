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


if __name__ == "__main__":
    unittest.main()
