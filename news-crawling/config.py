import os
from pathlib import Path

DB_PATH = Path(__file__).parent / "news.db"

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
