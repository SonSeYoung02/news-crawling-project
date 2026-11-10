import argparse
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _safe_log_text(text: str) -> str:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def run_pipeline() -> None:
    from crawlers import get_all_articles
    from db import init_db, is_duplicate, refresh_article_from_source, save_article

    logger.info("=== 원문 수집 시작: %s ===", datetime.now().isoformat())
    init_db()
    articles = get_all_articles()
    saved = refreshed = failed = 0
    for article in articles:
        if is_duplicate(article["url"]):
            if refresh_article_from_source(article):
                refreshed += 1
            else:
                failed += 1
        elif save_article(article):
            saved += 1
        else:
            failed += 1
    logger.info("=== 원문 수집 완료 | 수집: %d | 신규 저장: %d | 기존 갱신: %d | 실패: %d ===",
                len(articles), saved, refreshed, failed)


def run_scheduler() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler

    from config import SCHEDULE_HOUR, SCHEDULE_MINUTE

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_pipeline,
        trigger="cron",
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        id="daily_news_pipeline",
    )
    logger.info(
        "스케줄러 시작: 매일 %02d:%02d에 실행됩니다. 종료하려면 Ctrl+C",
        SCHEDULE_HOUR, SCHEDULE_MINUTE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="뉴스 원문 수집 파이프라인"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run", action="store_true", help="파이프라인 1회 즉시 실행")
    group.add_argument(
        "--schedule", action="store_true", help="매일 아침 자동 실행 스케줄러 시작"
    )
    args = parser.parse_args()

    if args.run:
        run_pipeline()
    elif args.schedule:
        run_scheduler()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
