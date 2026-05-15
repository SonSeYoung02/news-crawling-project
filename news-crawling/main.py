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


def _has_korean(text: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in text)


def run_pipeline() -> None:
    from crawlers import get_all_articles
    from db import (
        get_article_by_url,
        get_article_id_by_url,
        init_db,
        is_duplicate,
        save_analysis,
        save_article,
        update_content_if_empty,
    )
    from llm.analyzer import classify, summarize, translate_article_to_korean

    logger.info("=== 파이프라인 시작: %s ===", datetime.now().isoformat())
    init_db()

    # 1. 크롤링
    logger.info("뉴스 수집 중...")
    articles = get_all_articles()
    logger.info("총 %d건 수집 완료", len(articles))

    saved = skipped_dup = skipped_translation = 0

    for article in articles:
        # 2. 번역 (실패해도 원문으로 계속 진행)
        if article.get("translate_to_korean"):
            translated = translate_article_to_korean(
                article.get("title", ""),
                article.get("content", ""),
            )
            if translated:
                article["title"] = translated["title"]
                article["content"] = translated["content"]
            else:
                skipped_translation += 1
                logger.warning(
                    "번역 실패, 원문으로 저장: %s",
                    _safe_log_text(article["title"][:40]),
                )

        # 3. articles 테이블에 저장
        if is_duplicate(article["url"]):
            update_content_if_empty(article)
            skipped_dup += 1
            continue

        if not save_article(article):
            skipped_dup += 1
            continue

        saved += 1
        logger.info("저장: %s", _safe_log_text(article["title"][:40]))

        # 4. LLM 요약
        summary = summarize(article.get("content", ""))

        # 5. LLM 분류
        classification = classify(article.get("title", ""), article.get("content", ""))
        if classification["major_category"] == "기타" and article.get("major_category"):
            classification["major_category"] = article["major_category"]
        if not classification["sub_category"] and article.get("sub_category"):
            classification["sub_category"] = article["sub_category"]
        if not classification["tags"] and article.get("tags"):
            classification["tags"] = article["tags"]

        # 6. article_analysis 테이블에 저장
        article_id = get_article_id_by_url(article["url"])
        if article_id:
            save_analysis(
                article_id=article_id,
                summary=summary,
                major_category=classification["major_category"],
                sub_category=classification.get("sub_category", ""),
                tags=classification.get("tags", []),
            )

    logger.info(
        "=== 파이프라인 완료 | 수집: %d | 저장: %d | 중복 건너뜀: %d | 번역 실패: %d ===",
        len(articles), saved, skipped_dup, skipped_translation,
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
