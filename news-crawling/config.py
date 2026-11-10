from pathlib import Path

DB_PATH = Path(__file__).parent / "news.db"
MAJOR_CATEGORIES = ["AI", "IT", "경제", "국제"]

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
