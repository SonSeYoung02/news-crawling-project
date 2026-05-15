import json
import logging
import time
from typing import Optional

from config import GEMINI_API_KEY, GEMINI_MODEL, MAJOR_CATEGORIES

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """다음 뉴스 기사를 한국어로 3~5문장으로 요약해주세요.
기사가 외국어이면 먼저 한국어로 이해한 뒤, 핵심 내용만 자연스러운 한국어로 간결하게 작성하세요.

기사:
{content}

요약:"""

_TRANSLATE_ARTICLE_PROMPT = """다음 뉴스 기사의 제목과 본문을 자연스러운 한국어로 번역해주세요.
원문이 이미 한국어이면 의미를 유지하면서 어색한 표현만 다듬어주세요.
요약하지 말고 원문 정보를 유지하세요.

기사 제목: {title}
기사 본문:
{content}

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "title": "<한국어 제목>",
  "content": "<한국어 본문>"
}}"""

_CLASSIFY_PROMPT = """다음 뉴스 기사를 분류해주세요.

기사 제목: {title}
기사 내용: {content}

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "major_category": "<대분류: {categories} 중 하나>",
  "sub_category": "<중분류: 세부 주제 (예: 반도체, 주식시장, 대선, 교통사고 등)>",
  "tags": ["<키워드1>", "<키워드2>", "<키워드3>"]
}}"""

_client = None


def _get_client():
    """Gemini API 클라이언트를 반환한다. 최초 호출 시에만 초기화(싱글턴)."""
    global _client
    if _client is None:
        try:
            from google import genai
        except ImportError:
            raise ImportError("google-genai 패키지가 없습니다: pip install google-genai")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 환경 변수를 설정해주세요.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _has_korean(text: str) -> bool:
    """문자열에 한글(가~힣)이 하나 이상 포함되어 있으면 True를 반환한다."""
    return any("가" <= ch <= "힣" for ch in text)


def _call_gemini(prompt: str) -> Optional[str]:
    """Gemini 모델에 프롬프트를 전송하고 응답 텍스트를 반환한다.

    최대 3회 지수 백오프 재시도를 수행하며, 모든 시도 실패 시 None을 반환한다.
    """
    for attempt in range(3):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text.strip()
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                logger.warning("Gemini 호출 실패 (시도 %d/3), %ds 후 재시도: %s", attempt + 1, wait, e)
                time.sleep(wait)
            else:
                logger.error("Gemini 호출 최종 실패: %s", e)
    return None


def summarize(text: str) -> str:
    """뉴스 본문을 한국어 3~5문장으로 요약해 반환한다.

    텍스트가 없거나 20자 미만이면 빈 문자열을 반환한다.
    """
    if not text or len(text) < 20:
        return ""
    content = text[:3000]
    result = _call_gemini(_SUMMARY_PROMPT.format(content=content))
    return result or ""


def translate_article_to_korean(title: str, content: str) -> Optional[dict[str, str]]:
    """기사 제목과 본문을 한국어로 번역해 {"title": ..., "content": ...} 딕셔너리로 반환한다.

    번역 결과가 한국어가 아니거나 파싱에 실패하면 최대 3회 재시도하며,
    모두 실패하면 None을 반환한다.
    """
    source_text = content if content and len(content) >= 20 else title
    if not source_text:
        return None

    prompt = _TRANSLATE_ARTICLE_PROMPT.format(
        title=title,
        content=source_text[:5000],
    )

    for attempt in range(3):
        raw = _call_gemini(prompt)
        if not raw:
            if attempt < 2:
                time.sleep(2)
            continue

        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            logger.warning("LLM 번역 응답 파싱 실패 (시도 %d): %s", attempt + 1, raw[:200])
            if attempt < 2:
                time.sleep(2)
            continue

        try:
            result = json.loads(raw[start:end])
        except json.JSONDecodeError as e:
            logger.warning("LLM 번역 JSON 파싱 실패 (시도 %d): %s | raw=%s", attempt + 1, e, raw[:200])
            if attempt < 2:
                time.sleep(2)
            continue

        translated_title = str(result.get("title") or title).strip()
        translated_content = str(result.get("content") or "").strip()

        if not translated_content:
            if attempt < 2:
                time.sleep(2)
            continue

        if _has_korean(translated_title + translated_content[:300]):
            return {"title": translated_title, "content": translated_content}

        logger.warning("번역 결과가 한국어 아님 (시도 %d/3)", attempt + 1)
        if attempt < 2:
            time.sleep(2)

    return None


def translate_to_korean(title: str, content: str) -> str:
    """translate_article_to_korean의 래퍼로, 번역된 본문 문자열만 반환한다.

    번역 실패 시 빈 문자열을 반환한다.
    """
    result = translate_article_to_korean(title, content)
    return result["content"] if result else ""


def classify(title: str, content: str) -> dict:
    """기사를 대분류·중분류·태그로 분류해 딕셔너리로 반환한다.

    LLM 호출 실패 또는 파싱 오류 시 {"major_category": "기타", "sub_category": "", "tags": []}를 반환한다.
    """
    fallback = {"major_category": "기타", "sub_category": "", "tags": []}
    if not title:
        return fallback

    categories_str = "/".join(MAJOR_CATEGORIES)
    prompt = _CLASSIFY_PROMPT.format(
        title=title,
        content=content[:1500],
        categories=categories_str,
    )
    raw = _call_gemini(prompt)
    if not raw:
        return fallback

    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning("LLM 분류 응답 파싱 실패: %s", raw[:200])
        return fallback

    try:
        result = json.loads(raw[start:end])
        major = result.get("major_category", "기타")
        if major not in MAJOR_CATEGORIES:
            major = "기타"
        tags = result.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        return {
            "major_category": major,
            "sub_category": result.get("sub_category", ""),
            "tags": tags[:10],
        }
    except json.JSONDecodeError as e:
        logger.warning("LLM 분류 JSON 파싱 실패: %s | raw=%s", e, raw[:200])
        return fallback
