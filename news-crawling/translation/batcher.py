"""번역 대기열을 글자 수·건수 기준 묶음으로 나눈다."""
from config import BATCH_MAX_ARTICLES, BATCH_MAX_CHARS


def _size(job: dict) -> int:
    return len(job.get("title") or "") + len(job.get("content") or "")


def build_batches(
    queue: list[dict],
    max_chars: int = BATCH_MAX_CHARS,
    max_articles: int = BATCH_MAX_ARTICLES,
) -> list[list[dict]]:
    """순서를 유지하며 탐욕적으로 묶는다. 단독으로 한도를 넘는 기사는 홀로 한 묶음이 된다."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for job in queue:
        size = _size(job)
        if size > max_chars:
            if current:
                batches.append(current)
                current, current_chars = [], 0
            batches.append([job])
            continue
        if current and (current_chars + size > max_chars or len(current) >= max_articles):
            batches.append(current)
            current, current_chars = [], 0
        current.append(job)
        current_chars += size
    if current:
        batches.append(current)
    return batches
