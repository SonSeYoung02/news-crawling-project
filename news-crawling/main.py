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


def run_pipeline() -> None:
    from crawlers import get_all_articles
    from db import init_db, is_duplicate, save_articles_batch
    from llm.analyzer import classify, summarize

    logger.info("=== 파이프라인 시작: %s ===", datetime.now().isoformat())
    init_db()

    # 1. 크롤링
    logger.info("뉴스 수집 중...")
    articles = get_all_articles()
    logger.info("총 %d건 수집 완료", len(articles))

    # 2. 중복 필터링 + LLM 분석
    processed: list[dict] = []
    skipped_dup = 0
    for article in articles:
        if is_duplicate(article["url"]):
            skipped_dup += 1
            continue

        logger.info("분석 중: %s", article["title"][:40])

        summary = summarize(article.get("content", ""))
        classification = classify(article.get("title", ""), article.get("content", ""))

        article.update({
            "summary": summary,
            "major_category": classification["major_category"],
            "sub_category": classification["sub_category"],
            "tags": classification["tags"],
        })
        processed.append(article)

    # 3. 저장
    saved, skipped_save = save_articles_batch(processed)
    logger.info(
        "=== 파이프라인 완료 | 수집: %d | 중복 건너뜀: %d | 저장: %d | 저장 중복: %d ===",
        len(articles), skipped_dup, saved, skipped_save,
    )


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
        description="한국어 뉴스 크롤링 + LLM 분석 파이프라인"
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
