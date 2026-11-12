import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import (
    CUTOFF_HOUR,
    CUTOFF_MINUTE,
    DEADLINE_HOUR,
    DEADLINE_MINUTE,
    GEMINI_DAILY_LIMIT,
    GEMINI_RPM_LIMIT,
    REQUEST_INTERVAL_SECONDS,
)
from db import get_daily_quota, increment_daily_quota

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


class RateLimiter:
    """무료 API 한도(RPM, 일일 RPD)를 엄격히 준수하고 요청 간격을 제어한다.
    일일 사용량을 SQLite에 영속화하여 프로세스 재시작에도 한도를 초과하지 않는다."""

    def __init__(
        self,
        daily_limit: int = GEMINI_DAILY_LIMIT,
        rpm_limit: int = GEMINI_RPM_LIMIT,
        request_interval: float = REQUEST_INTERVAL_SECONDS,
    ):
        self.daily_limit = daily_limit
        self.rpm_limit = rpm_limit
        self.request_interval = request_interval
        self._last_request_time: float = 0.0

    def _get_today_str(self) -> str:
        return datetime.now(KST).strftime("%Y-%m-%d")

    def can_consume(self, requests: int = 1) -> bool:
        today_str = self._get_today_str()
        quota = get_daily_quota(today_str)
        current_count = quota.get("request_count", 0)
        return (current_count + requests) <= self.daily_limit

    def wait_and_consume(self, tokens: int = 0, requests: int = 1) -> bool:
        if not self.can_consume(requests):
            today_str = self._get_today_str()
            quota = get_daily_quota(today_str)
            logger.warning(
                "Gemini 일일 무료 한도(%d회)에 도달하였습니다. 오늘 사용량: %d회",
                self.daily_limit,
                quota.get("request_count", 0),
            )
            return False

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.request_interval and self.request_interval > 0:
            wait_time = self.request_interval - elapsed
            time.sleep(wait_time)

        today_str = self._get_today_str()
        increment_daily_quota(today_str, requests=requests, tokens=tokens)
        self._last_request_time = time.time()
        return True

    def handle_rate_limit_error(self, backoff_seconds: float = 15.0) -> None:
        """429 또는 일시적 한도 오류 시 지수 백오프 대기"""
        logger.warning("Rate limit 발생. %0.1f초간 대기합니다.", backoff_seconds)
        time.sleep(backoff_seconds)


class CutoffController:
    """새벽 05:55 이후 신규 요청을 중단하고 06:00 이전에 안전하게 종료되도록 통제한다."""

    def __init__(
        self,
        cutoff_hour: int = CUTOFF_HOUR,
        cutoff_minute: int = CUTOFF_MINUTE,
        deadline_hour: int = DEADLINE_HOUR,
        deadline_minute: int = DEADLINE_MINUTE,
    ):
        self.cutoff_hour = cutoff_hour
        self.cutoff_minute = cutoff_minute
        self.deadline_hour = deadline_hour
        self.deadline_minute = deadline_minute

    def can_request(self, now_dt: Optional[datetime] = None) -> bool:
        """KST 기준 05:55:00 ~ 06:00:00 사이에는 신규 번역 요청을 차단한다."""
        if now_dt is None:
            now_dt = datetime.now(KST)
        elif now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=KST)

        h = now_dt.hour
        m = now_dt.minute

        # 05:55 이상 06:00 미만인 경우 신규 요청 차단
        if h == self.cutoff_hour and m >= self.cutoff_minute:
            return False
        # 06:00 이상 07:00 미만(마감 초과 구간) 차단
        if h == self.deadline_hour and m < 60:
            return False

        return True
