import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
temp_db_path = temp_db.name
temp_db.close()

os.environ["DB_PATH"] = temp_db_path

import db
from translation.rate_limiter import CutoffController, RateLimiter

KST = timezone(timedelta(hours=9))


class TestRateLimiterAndCutoff(unittest.TestCase):
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

    def test_rate_limiter_daily_budget_and_persistence(self):
        limiter1 = RateLimiter(daily_limit=5, request_interval=0.01)

        for _ in range(5):
            self.assertTrue(limiter1.wait_and_consume(tokens=50))

        # 6번째 호출은 일일 한도 초과로 차단
        self.assertFalse(limiter1.wait_and_consume(tokens=50))

        # 새 인스턴스를 생성해도 DB 영속화 덕분에 여전히 한도 초과
        limiter2 = RateLimiter(daily_limit=5, request_interval=0.01)
        self.assertFalse(limiter2.wait_and_consume(tokens=50))

    def test_cutoff_controller_time_boundaries(self):
        controller = CutoffController(cutoff_hour=5, cutoff_minute=55, deadline_hour=6, deadline_minute=0)

        # 1. 05:54:59 (마감 전 -> 허용)
        t_before = datetime(2026, 11, 12, 5, 54, 59, tzinfo=KST)
        self.assertTrue(controller.can_request(now_dt=t_before))

        # 2. 05:55:00 정각 (마감 도달 -> 차단)
        t_cutoff = datetime(2026, 11, 12, 5, 55, 0, tzinfo=KST)
        self.assertFalse(controller.can_request(now_dt=t_cutoff))

        # 3. 05:58:30 (마감 시간대 -> 차단)
        t_mid = datetime(2026, 11, 12, 5, 58, 30, tzinfo=KST)
        self.assertFalse(controller.can_request(now_dt=t_mid))

        # 4. 01:30:00 (정상 새벽 시간 -> 허용)
        t_normal = datetime(2026, 11, 12, 1, 30, 0, tzinfo=KST)
        self.assertTrue(controller.can_request(now_dt=t_normal))


if __name__ == "__main__":
    unittest.main()
