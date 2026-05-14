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
        init_db,
        is_duplicate,
        save_articles_batch,
        update_article_translation,
        update_content_if_empty,
    )
    from llm.analyzer import classify, summarize, translate_article_to_korean

    logger.info("=== 파이프라인 시작: %s ===", datetime.now().isoformat())
    init_db()

    # 1. 크롤링
    logger.info("뉴스 수집 중...")
    articles = get_all_articles()
    logger.info("총 %d건 수집 완료", len(articles))

    # 2. 중복 필터링 + LLM 분석
    processed: list[dict] = []
    skipped_dup = 0
    skipped_translation = 0
    updated_translation = 0
    for article in articles:
        if is_duplicate(article["url"]):
            existing = get_article_by_url(article["url"])
            existing_text = f"{existing.get('title', '')}\n{existing.get('content', '')}" if existing else ""
            if article.get("translate_to_korean") and not _has_korean(existing_text):
                logger.info("기존 외국어 기사 한국어 갱신 중: %s", _safe_log_text(article["title"][:40]))
                translated = translate_article_to_korean(
                    article.get("title", ""),
                    article.get("content", ""),
                )
                if translated:
                    article["title"] = translated["title"]
                    article["content"] = translated["content"]
                    summary = summarize(article.get("content", ""))
                    classification = classify(article.get("title", ""), article.get("content", ""))
                    if classification["major_category"] == "기타" and article.get("major_category"):
                        classification["major_category"] = article["major_category"]
                    if not classification["sub_category"] and article.get("sub_category"):
                        classification["sub_category"] = article["sub_category"]
                    if not classification["tags"] and article.get("tags"):
                        classification["tags"] = article["tags"]
                    article.update({
                        "summary": summary,
                        "major_category": classification["major_category"],
                        "sub_category": classification["sub_category"],
                        "tags": classification["tags"],
                    })
                    if update_article_translation(article):
                        updated_translation += 1
                else:
                    skipped_translation += 1
            update_content_if_empty(article)
            skipped_dup += 1
            continue

        logger.info("분석 중: %s", _safe_log_text(article["title"][:40]))

        if article.get("translate_to_korean"):
            translated = translate_article_to_korean(
                article.get("title", ""),
                article.get("content", ""),
            )
            if not translated:
                skipped_translation += 1
                logger.warning("한국어 변환 실패로 저장 건너뜀: %s", _safe_log_text(article["title"][:40]))
                continue
            article["title"] = translated["title"]
            article["content"] = translated["content"]

        summary = summarize(article.get("content", ""))
        classification = classify(article.get("title", ""), article.get("content", ""))
        if classification["major_category"] == "기타" and article.get("major_category"):
            classification["major_category"] = article["major_category"]
        if not classification["sub_category"] and article.get("sub_category"):
            classification["sub_category"] = article["sub_category"]
        if not classification["tags"] and article.get("tags"):
            classification["tags"] = article["tags"]

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
        "=== 파이프라인 완료 | 수집: %d | 중복 건너뜀: %d | 번역 갱신: %d | 번역 실패: %d | 저장: %d | 저장 중복: %d ===",
        len(articles), skipped_dup, updated_translation, skipped_translation, saved, skipped_save,
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
