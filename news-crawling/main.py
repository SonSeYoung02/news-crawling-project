import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

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


def crawl_and_save_articles(articles: Optional[list[dict]] = None) -> tuple[int, int, int, set[int]]:
    """외부 소스로부터 기사를 수집하여 원문 그대로 articles 테이블에 우선 저장한다.
    요약이나 분류 API는 일체 호출하지 않는다.
    반환값: (신규 저장 건수, 기존 갱신 건수, 실패 건수, 신규 기사 ID 세트)"""
    from db import get_article_id_by_url, is_duplicate, refresh_article_from_source, save_article

    if articles is None:
        from crawlers import get_all_articles
        logger.info("뉴스 소스 수집 시작...")
        articles = get_all_articles()
        logger.info("총 %d건 수집 완료", len(articles))

    saved = refreshed = failed = 0
    new_ids: set[int] = set()

    for article in articles:
        url = article.get("url")
        if not url:
            failed += 1
            continue

        if is_duplicate(url):
            if refresh_article_from_source(article):
                refreshed += 1
            else:
                failed += 1
        else:
            if save_article(article):
                saved += 1
                aid = get_article_id_by_url(url)
                if aid:
                    new_ids.add(aid)
            else:
                failed += 1

    logger.info("원문 수집 및 저장 완료 | 수집: %d | 신규: %d | 갱신: %d | 실패: %d",
                len(articles), saved, refreshed, failed)
    return saved, refreshed, failed, new_ids


def run_pipeline(
    sample_articles: Optional[list[dict]] = None,
    is_manual: bool = False,
    cutoff_controller: Optional[object] = None,
    rate_limiter: Optional[object] = None,
) -> dict:
    """새벽 뉴스 수집 및 Gemini 묶음 번역 파이프라인.
    1. 프로세스 락 획득 (중복 실행 방지)
    2. 뉴스 수집 및 원문 즉시 저장 (요약/분류 배제)
    3. 번역 대기열 생성 (신규 기사 최우선, 한국어 소스 배제)
    4. 묶음 번역 수행 (여러 기사를 Gemini 1회 요청으로 번역, 05:55 마감·일일 20회 한도 제어)
    5. 프로세스 락 해제
    """
    from db import acquire_crawl_lock, init_db, release_crawl_lock
    from translation.queue import get_pending_translation_queue
    from translation.rate_limiter import CutoffController, RateLimiter
    from translation.batch_translator import translate_batch
    from translation.batcher import build_batches

    logger.info("=== 새벽 뉴스 수집·번역 파이프라인 시작: %s ===", datetime.now().isoformat())

    if not acquire_crawl_lock("nightly_crawl"):
        logger.warning("이미 다른 크롤러 파이프라인 인스턴스가 실행 중입니다. 실행을 건너뜁니다.")
        return {"status": "already_running", "saved": 0, "refreshed": 0, "translated": 0}

    init_db()

    if cutoff_controller is None:
        cutoff_controller = CutoffController()
    if rate_limiter is None:
        rate_limiter = RateLimiter()

    status = "completed"
    saved = refreshed = failed_crawl = 0
    translated_count = failed_translation_count = pending_translation_count = 0

    try:
        # 1. 수집 및 원문 즉시 저장
        saved, refreshed, failed_crawl, new_ids = crawl_and_save_articles(sample_articles)

        # 2. 번역 대기열 생성
        queue = get_pending_translation_queue(new_ids)

        # 3. 묶음 번역 루프 (Gemini 1회 요청에 여러 기사)
        batches = build_batches(queue)
        permanent_streak = 0
        for idx, batch in enumerate(batches):
            # 05:55 마감 검사
            if not cutoff_controller.can_request():
                logger.info("새벽 마감 시간(05:55)에 도달하여 신규 번역 작업을 안전하게 중단합니다.")
                status = "stopped_cutoff"
                pending_translation_count += sum(len(b) for b in batches[idx:])
                break

            logger.info("묶음 번역 [%d/%d] %d건", idx + 1, len(batches), len(batch))
            outcome = translate_batch(batch, rate_limiter)
            translated_count += len(outcome.completed_ids)
            failed_translation_count += len(outcome.failed_ids)
            pending_translation_count += len(outcome.pending_ids)

            if outcome.stop_reason == "daily_quota":
                logger.warning("일일 무료 API 한도에 도달하여 번역 작업을 중단합니다.")
                status = "stopped_daily_quota"
                pending_translation_count += sum(len(b) for b in batches[idx + 1:])
                break
            if outcome.stop_reason == "permanent_error":
                permanent_streak += 1
                if permanent_streak >= 2:
                    logger.error("영구 오류가 연속 2회 발생하여 번역 작업을 중단합니다.")
                    status = "stopped_permanent_error"
                    pending_translation_count += sum(len(b) for b in batches[idx + 1:])
                    break
            else:
                permanent_streak = 0

    except Exception as e:
        logger.error("파이프라인 실행 중 예외 발생: %s", e, exc_info=True)
        status = "failed"
    finally:
        release_crawl_lock("nightly_crawl")

    logger.info(
        "=== 파이프라인 종료 | 수집: %d (신규 %d, 갱신 %d, 실패 %d) | 번역 완료: %d | 실패: %d | 미완료: %d | 최종 상태: %s ===",
        saved + refreshed, saved, refreshed, failed_crawl,
        translated_count, failed_translation_count, pending_translation_count, status,
    )
    return {
        "status": status,
        "saved": saved,
        "refreshed": refreshed,
        "failed_crawl": failed_crawl,
        "translated": translated_count,
        "failed_translation": failed_translation_count,
        "pending_translation": pending_translation_count,
    }


def run_scheduler() -> None:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from config import SCHEDULE_HOUR, SCHEDULE_MINUTE

    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone="Asia/Seoul",
        ),
        id="nightly_crawl_job",
        name="새벽 뉴스 수집 및 번역",
        replace_existing=True,
    )
    logger.info(
        "스케줄러 시작: 매일 %02d:%02d KST에 파이프라인이 실행됩니다. (종료: Ctrl+C)",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러를 안전하게 종료합니다.")


def main() -> None:
    from config import SCHEDULE_HOUR, SCHEDULE_MINUTE

    parser = argparse.ArgumentParser(
        description="새벽 뉴스 수집 및 Gemini 묶음 번역 파이프라인"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run", action="store_true", help="파이프라인 1회 즉시 실행")
    group.add_argument(
        "--schedule",
        action="store_true",
        help=f"매일 {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} KST 스케줄러 실행",
    )
    args = parser.parse_args()

    if args.run:
        run_pipeline(is_manual=True)
    elif args.schedule:
        run_scheduler()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
