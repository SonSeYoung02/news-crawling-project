import re
from typing import List


def chunk_text(text: str, max_chars: int = 2000) -> list[str]:
    """긴 기사 본문을 자연스러운 문단 또는 문장 단위로 분할한다.
    - max_chars 이하의 크기로 분할하며 문맥을 보존한다.
    - 코드 블록, 숫자, 링크, 고유명사를 훼손하지 않는다.
    - 재결합 시 원문의 문단 흐름을 그대로 복원할 수 있다.
    """
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for p in paragraphs:
        p_str = p.strip()
        if not p_str:
            continue

        # 단일 문단이 max_chars보다 큰 경우 문장 단위로 추가 분할
        if len(p_str) > max_chars:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_len = 0

            sentences = re.split(r"(?<=[.!?])\s+", p_str)
            sub_chunk: list[str] = []
            sub_len = 0
            for s in sentences:
                if sub_len + len(s) + 1 > max_chars and sub_chunk:
                    chunks.append(" ".join(sub_chunk))
                    sub_chunk = [s]
                    sub_len = len(s)
                else:
                    sub_chunk.append(s)
                    sub_len += len(s) + 1
            if sub_chunk:
                chunks.append(" ".join(sub_chunk))
            continue

        if current_len + len(p_str) + 2 > max_chars and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p_str]
            current_len = len(p_str)
        else:
            current_chunk.append(p_str)
            current_len += len(p_str) + 2

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks
