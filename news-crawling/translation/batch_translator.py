import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from google.genai import types

import db
from config import GEMINI_MODEL, MIN_TRANSLATION_RATIO
from translation import translator
from translation.translator import TRANSLATION_SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

DEFAULT_RETRY_SECONDS = 60.0
TRANSIENT_RETRY_SECONDS = 10.0
RATIO_CHECK_MIN_CHARS = 200

BATCH_SYSTEM_INSTRUCTION = (
    TRANSLATION_SYSTEM_INSTRUCTION
    + "\n5. 입력은 JSON 배열이며 각 항목은 id, title, content를 가집니다. "
    "각 항목을 같은 id로 번역해 [{\"id\", \"title\", \"content\"}] 형태의 JSON 배열만 출력하십시오."
)


class DailyQuotaExceeded(Exception):
    """일일 요청 한도(PerDay) 소진."""


class MinuteRateLimited(Exception):
    """분당 한도 초과 또는 일시적 오류. retry_seconds 후 재시도한다."""

    def __init__(self, message: str = "", retry_seconds: float = DEFAULT_RETRY_SECONDS):
        super().__init__(message)
        self.retry_seconds = retry_seconds


class PermanentApiError(Exception):
    """재시도해도 해결되지 않는 요청 오류(400·403·404)."""


class BatchParseError(Exception):
    """응답 JSON 자체를 해석할 수 없음."""


def _has_korean(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)


def _parse_retry_delay(details: Any) -> float:
    """details 안의 RetryInfo.retryDelay("37s", "37.5s")를 초 단위로 찾는다. 없으면 기본값."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            delay = node.get("retryDelay")
            if isinstance(delay, str):
                found.append(delay)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(details)
    for delay in found:
        m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)s\s*", delay)
        if m:
            return float(m.group(1))
    return DEFAULT_RETRY_SECONDS


def classify_api_error(e: Exception) -> Exception:
    """Gemini API 예외를 DailyQuotaExceeded / MinuteRateLimited / PermanentApiError로 변환한다."""
    code = getattr(e, "code", None)
    message = str(getattr(e, "message", "") or "")
    details = getattr(e, "details", None)

    if code == 429:
        # 일일 한도 응답에도 RetryInfo가 있으므로 PerDay 판별을 우선한다.
        if "PerDay" in f"{message} {details}":
            return DailyQuotaExceeded(message or str(e))
        return MinuteRateLimited(message or str(e), retry_seconds=_parse_retry_delay(details))
    if code in (400, 403, 404):
        return PermanentApiError(message or str(e))
    return MinuteRateLimited(message or str(e), retry_seconds=TRANSIENT_RETRY_SECONDS)


def call_gemini_batch(batch: list[dict], model: str = GEMINI_MODEL) -> str:
    """여러 기사를 한 번의 Gemini 요청으로 번역하고 원시 응답 텍스트를 반환한다."""
    payload = [
        {"id": job["article_id"], "title": job.get("title", ""), "content": job.get("content", "")}
        for job in batch
    ]
    contents = "다음 JSON 배열의 기사들을 한국어로 번역해 주세요:\n\n" + json.dumps(payload, ensure_ascii=False)
    config = types.GenerateContentConfig(
        system_instruction=BATCH_SYSTEM_INSTRUCTION,
        temperature=0.2,
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    try:
        client = translator.get_gemini_client()
    except ValueError as e:
        logger.error("Gemini 클라이언트 생성 실패 (API 키 확인 필요): %s", e)
        raise PermanentApiError(str(e)) from e
    try:
        response = client.models.generate_content(model=model, contents=contents, config=config)
        return response.text or ""
    except Exception as e:
        logger.error("Gemini 묶음 번역 호출 오류 (model=%s): %s", model, e)
        raise classify_api_error(e) from e


def _strip_code_fence(raw: str) -> str:
    text = raw.strip()
    m = re.match(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```$", text, re.DOTALL)
    return m.group(1).strip() if m else text


def _validity_problem(item: dict, source: dict) -> str:
    """검증 실패 사유를 반환한다. 통과하면 빈 문자열."""
    title = item.get("title")
    content = item.get("content")
    title = title.strip() if isinstance(title, str) else ""
    content = content if isinstance(content, str) else ""
    src_content = source.get("content") or ""

    if not title:
        return "번역 제목이 비어 있음"
    if src_content.strip() and not content.strip():
        return "원문 본문이 있으나 번역 본문이 비어 있음"
    if not _has_korean(title + content[:300]):
        return "번역 결과에 한글이 없음"
    if len(src_content) >= RATIO_CHECK_MIN_CHARS and len(content) < MIN_TRANSLATION_RATIO * len(src_content):
        return "번역문이 원문 대비 너무 짧아 요약 의심"
    return ""


def parse_batch_response(raw: str, batch: list[dict]) -> dict[int, dict]:
    """응답을 파싱하고 검증을 통과한 {article_id: {"title", "content"}}만 반환한다."""
    try:
        data = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError) as e:
        raise BatchParseError(f"응답 JSON 파싱 실패: {e}") from e

    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        if len(data) == 1 and len(lists) == 1:
            data = lists[0]
    if not isinstance(data, list):
        raise BatchParseError("응답 최상위가 JSON 배열이 아닙니다.")

    sources = {job["article_id"]: job for job in batch}
    seen: dict[int, dict] = {}
    duplicates: set[int] = set()

    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            logger.warning("응답 항목 형식이 올바르지 않아 건너뜁니다: %.80r", item)
            continue
        try:
            article_id = int(item["id"])
        except (TypeError, ValueError):
            logger.warning("응답 id를 정수로 변환할 수 없어 건너뜁니다: %r", item["id"])
            continue
        if article_id not in sources:
            logger.warning("입력에 없는 id 제외 (기사 ID: %d)", article_id)
            continue
        if article_id in seen or article_id in duplicates:
            duplicates.add(article_id)
            seen.pop(article_id, None)
            logger.warning("응답에 중복된 id가 있어 제외합니다. (기사 ID: %d)", article_id)
            continue
        seen[article_id] = item

    result: dict[int, dict] = {}
    for article_id, item in seen.items():
        problem = _validity_problem(item, sources[article_id])
        if problem:
            logger.warning("번역 검증 실패로 제외 (기사 ID: %d): %s", article_id, problem)
            continue
        content = item.get("content")
        result[article_id] = {
            "title": item["title"].strip(),
            "content": content if isinstance(content, str) else "",
        }
    return result


MAX_MINUTE_WAIT_SECONDS = 60


@dataclass
class BatchOutcome:
    completed_ids: list[int] = field(default_factory=list)
    pending_ids: list[int] = field(default_factory=list)  # 상태 변경 없이 다음 실행으로 넘김
    failed_ids: list[int] = field(default_factory=list)  # fail_article_translation 기록됨
    stop_reason: Optional[str] = None  # None | "daily_quota" | "permanent_error"


def _merge_outcomes(first: BatchOutcome, second: BatchOutcome) -> BatchOutcome:
    return BatchOutcome(
        completed_ids=first.completed_ids + second.completed_ids,
        pending_ids=first.pending_ids + second.pending_ids,
        failed_ids=first.failed_ids + second.failed_ids,
        stop_reason=first.stop_reason or second.stop_reason,
    )


def translate_batch(
    batch: list[dict],
    rate_limiter,
    model: str = GEMINI_MODEL,
    allow_split: bool = True,
) -> BatchOutcome:
    """기사 묶음을 한 번의 Gemini 요청으로 번역해 DB에 저장한다."""
    outcome = BatchOutcome()
    todo: list[dict] = []
    for job in batch:
        row = db.get_or_create_translation(job["article_id"], job["content_hash"])
        if row.get("status") == "completed":
            outcome.completed_ids.append(job["article_id"])
        else:
            todo.append(job)
    if not todo:
        return outcome

    todo_ids = [job["article_id"] for job in todo]
    tokens = sum(len(job.get("title") or "") + len(job.get("content") or "") for job in todo)
    results: dict[int, dict] = {}

    for attempt in range(2):
        # 재시도를 포함해 Gemini 호출 1회마다 요청 1회를 소비한다.
        if not rate_limiter.wait_and_consume(tokens=tokens, requests=1):
            logger.warning("일일 요청 한도로 묶음 번역을 중단합니다. (기사 %d건 보류)", len(todo_ids))
            outcome.pending_ids.extend(todo_ids)
            outcome.stop_reason = "daily_quota"
            return outcome
        try:
            raw = call_gemini_batch(todo, model=model)
            results = parse_batch_response(raw, todo)
            break
        except DailyQuotaExceeded:
            logger.warning("Gemini 일일 한도 소진: 묶음 번역을 중단합니다. (기사 %d건 보류)", len(todo_ids))
            outcome.pending_ids.extend(todo_ids)
            outcome.stop_reason = "daily_quota"
            return outcome
        except MinuteRateLimited as e:
            if attempt == 0:
                wait = min(e.retry_seconds, MAX_MINUTE_WAIT_SECONDS)
                logger.warning("분당 한도/일시 오류: %s초 대기 후 1회 재시도합니다.", wait)
                time.sleep(wait)
                continue
            logger.warning("재시도 후에도 분당 한도/일시 오류가 계속되어 %d건을 보류합니다.", len(todo_ids))
            outcome.pending_ids.extend(todo_ids)
            return outcome
        except PermanentApiError as e:
            logger.error("묶음 번역 영구 오류: %s", e)
            for article_id, job in zip(todo_ids, todo):
                db.fail_article_translation(article_id, job["content_hash"], f"묶음 번역 실패: {e}")
            outcome.failed_ids.extend(todo_ids)
            outcome.stop_reason = "permanent_error"
            return outcome
        except BatchParseError as e:
            if allow_split and len(todo) >= 2:
                logger.warning("묶음 응답 파싱 실패(%s): 절반으로 나누어 재시도합니다.", e)
                mid = len(todo) // 2
                first = translate_batch(todo[:mid], rate_limiter, model, allow_split=False)
                if first.stop_reason:
                    rest = BatchOutcome(pending_ids=[j["article_id"] for j in todo[mid:]])
                else:
                    rest = translate_batch(todo[mid:], rate_limiter, model, allow_split=False)
                merged = _merge_outcomes(first, rest)
                return _merge_outcomes(outcome, merged)
            logger.warning("묶음 응답 파싱 실패(%s): %d건을 보류합니다.", e, len(todo_ids))
            outcome.pending_ids.extend(todo_ids)
            return outcome

    for job in todo:
        article_id = job["article_id"]
        result = results.get(article_id)
        if result and db.complete_article_translation(
            article_id, job["content_hash"], result["title"], result["content"], model
        ):
            outcome.completed_ids.append(article_id)
        else:
            outcome.pending_ids.append(article_id)
    return outcome
