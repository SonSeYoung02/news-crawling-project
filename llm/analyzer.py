import json
import logging
from typing import Optional

from config import GEMINI_API_KEY, GEMINI_MODEL, MAJOR_CATEGORIES

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = """다음 뉴스 기사를 한국어로 3~5문장으로 요약해주세요. 핵심 내용만 간결하게 작성하세요.

기사:
{content}

요약:"""

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
    global _client
    if _client is None:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai 패키지가 없습니다: pip install google-generativeai")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY 환경 변수를 설정해주세요.")
        genai.configure(api_key=GEMINI_API_KEY)
        _client = genai.GenerativeModel(GEMINI_MODEL)
    return _client


def _call_gemini(prompt: str) -> Optional[str]:
    try:
        model = _get_client()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error("Gemini 호출 실패: %s", e)
        return None


def summarize(text: str) -> str:
    if not text or len(text) < 50:
        return ""
    content = text[:3000]
    result = _call_gemini(_SUMMARY_PROMPT.format(content=content))
    return result or ""


def classify(title: str, content: str) -> dict:
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
