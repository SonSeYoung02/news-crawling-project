import os
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", str(Path(__file__).parent / "news.db")))
ENV_PATH = Path(__file__).parent / ".env"


def _load_env_file() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# gemini-2.5-flash는 무료 티어 후보 모델이며, 프로젝트의 실제 무료 가용성에 따라 설정으로 변경 가능합니다.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
REQUIRE_FREE_TIER = os.environ.get("REQUIRE_FREE_TIER", "true").lower() in ("true", "1", "yes")

# 무료 API 한도 통제 설정
# 무료 티어 기준: RPM(분당 요청 수), RPD(일일 요청 수)
GEMINI_RPM_LIMIT = int(os.environ.get("GEMINI_RPM_LIMIT", "10"))
# gemini-2.5-flash 무료 RPD는 20 (2026-11 로그 기준)
GEMINI_DAILY_LIMIT = int(os.environ.get("GEMINI_DAILY_LIMIT", "20"))
# 묶음 번역: 요청 1회에 담을 최대 글자 수/기사 수
BATCH_MAX_CHARS = int(os.environ.get("BATCH_MAX_CHARS", "12000"))
BATCH_MAX_ARTICLES = int(os.environ.get("BATCH_MAX_ARTICLES", "10"))
# 한국어 판별 비율 임계값, 번역문/원문 최소 길이 비율
KOREAN_RATIO_THRESHOLD = float(os.environ.get("KOREAN_RATIO_THRESHOLD", "0.3"))
MIN_TRANSLATION_RATIO = float(os.environ.get("MIN_TRANSLATION_RATIO", "0.3"))
REQUEST_INTERVAL_SECONDS = float(os.environ.get("REQUEST_INTERVAL_SECONDS", "6.0"))

# 새벽 스케줄 및 마감 설정 (KST 기준)
SCHEDULE_HOUR = int(os.environ.get("SCHEDULE_HOUR", "1"))
SCHEDULE_MINUTE = int(os.environ.get("SCHEDULE_MINUTE", "0"))
CUTOFF_HOUR = int(os.environ.get("CUTOFF_HOUR", "5"))
CUTOFF_MINUTE = int(os.environ.get("CUTOFF_MINUTE", "55"))
DEADLINE_HOUR = int(os.environ.get("DEADLINE_HOUR", "6"))
DEADLINE_MINUTE = int(os.environ.get("DEADLINE_MINUTE", "0"))

# 긴 기사 분할 크기 (문자 수 기준, 약 1,500 ~ 2,000자)
CHUNK_MAX_CHARS = int(os.environ.get("CHUNK_MAX_CHARS", "2000"))

MAJOR_CATEGORIES = ["AI", "IT", "경제", "국제"]

CRAWL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15
