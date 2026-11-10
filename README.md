# AI·기술 뉴스 원문 수집 및 뷰어

국내외 뉴스·개발 커뮤니티·논문·오픈소스 소식을 수집해 원문으로 제공하는 프로젝트입니다. Gemini 의존성을 제거했으며 자동 번역·요약·AI 분류를 수행하지 않습니다. 별도 API 키 없이 수집합니다.

## 프로젝트 구성

| 영역 | 경로 | 역할 |
|---|---|---|
| 크롤러 | `news-crawling/` | 여러 출처의 제목·본문 및 메타데이터 수집 |
| 백엔드 | `news-viewer/backend/` | FastAPI 기반 조회 API |
| 프론트엔드 | `news-viewer/frontend/` | React·Vite 기반 뉴스 뷰어 |
| 통합 실행 | `start.ps1` | 뷰어 실행, `-Crawl`로 수집 함께 실행 |

크롤러와 백엔드는 `news-crawling/news.db` SQLite 파일을 공유합니다. 카테고리는 수집기에서 제공하는 값을 사용합니다. 기존 분석 데이터는 호환성을 위해 보존하며 뷰어는 수집 원문을 사용합니다.

## 수집 출처

네이버뉴스, Google News, GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to를 지원합니다. 출처의 상태·요청 제한에 따라 소스별 수집량은 달라질 수 있습니다.

수집 내용은 본문·피드 내용·논문 초록 등 출처에서 제공되는 텍스트이며, 모든 출처가 기사 전문을 제공하는 것은 아닙니다. 해외 기사는 원문 언어로 표시합니다.

## 실행

Python 가상환경과 Node.js를 준비합니다.

```powershell
# 크롤러
cd news-crawling
python -m pip install -r requirements.txt
python main.py --run
# 매일 한국 시간 08:00에 수집할 경우
python main.py --schedule
```

```powershell
# 백엔드
cd news-viewer/backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

```powershell
# 프론트엔드
cd news-viewer/frontend
npm ci
npm run dev
```

뷰어: http://localhost:5173 / API 문서: http://localhost:8000/docs

## 데이터 관리

- URL로 중복 수집을 확인하고 기존 기사는 재수집한 원문으로 갱신합니다.
- DB·로그·가상환경·환경 파일은 커밋하지 않습니다.
- 뷰어의 검색·출처 필터·카테고리·상세보기로 기사를 탐색하고 원문 링크에서 출처를 확인합니다.
- 프론트엔드 검증은 `npm run build`, 크롤러 검증은 `python -m unittest test_direct_content -v`를 사용합니다.
