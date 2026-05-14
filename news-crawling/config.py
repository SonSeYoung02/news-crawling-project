import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "news.db"
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
GEMINI_MODEL = "gemini-2.5-flash"

MAJOR_CATEGORIES = ["IT", "경제", "정치", "사회", "스포츠", "연예", "국제"]

SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 0

CRAWL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 10
