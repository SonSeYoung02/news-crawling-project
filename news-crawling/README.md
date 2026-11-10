> 현재 동작: 기사별 AI 요약은 생성하지 않습니다. 신규 수집과 누락 분석 보완 모두 번역·분류만 수행합니다. 기존 summary 데이터는 호환성을 위해 보존하며 신규 분석의 summary는 빈 문자열입니다.

# AI·IT 뉴스 크롤링 + LLM 분석 파이프라인

네이버뉴스, Google News, GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to에서 최신 뉴스를 수집하고 Gemini AI로 한국어 번역·분류하여 SQLite에 저장하는 파이프라인입니다.

---

## 목차

- [구조](#구조)
- [동작 로직](#동작-로직)
- [설치](#설치)
- [설정](#설정)
- [사용법](#사용법)
- [DB 확인](#db-확인)

---

## 구조

```
news-crawling/
├── main.py                  # 진입점 (CLI)
├── config.py                # 환경 설정 (API 키, DB 경로, 스케줄 등)
├── db.py                    # SQLite 연결 및 저장 로직
├── crawlers/
│   ├── __init__.py          # 전체 소스 통합 (get_all_articles)
│   ├── naver.py             # 네이버뉴스 크롤러 (HTML 파싱)
│   ├── google_news.py       # Google News 글로벌 크롤러 (RSS)
│   ├── geeknews.py          # GeekNews 크롤러 (Atom/RSS)
│   ├── reddit_ai.py         # Reddit AI 서브레딧 크롤러 (RSS)
│   ├── github_trending.py   # GitHub Trending 오픈소스 크롤러 (HTML)
│   ├── huggingface.py       # Hugging Face 블로그/논문 크롤러 (RSS/HTML)
│   ├── arxiv.py             # arXiv API 크롤러
│   ├── devto.py             # dev.to API 크롤러
│   └── _rss.py              # RSS 공통 파서
├── llm/
│   └── analyzer.py          # Gemini API 번역·분류
├── news.db                  # SQLite DB (실행 후 생성)
├── pipeline.log             # 실행 로그 (실행 후 생성)
└── requirements.txt
```

---

## 동작 로직

```
┌─────────────────────────────────────────────────────┐
│                       main.py                       │
│                    run_pipeline()                   │
└──────────────────────────┬──────────────────────────┘
                           │
                 ① 뉴스 수집 (크롤링)
                           │
     ┌─────────────────────▼─────────────────────┐
     │            crawlers/__init__.py           │
     │             get_all_articles()            │
     └─┬──────┬──────┬──────┬──────┬──────┬──────┘
       │      │      │      │      │      │
    네이버  Google  Geek   Reddit GitHub Hugging arXiv dev.to
    (HTML)  (RSS)  (Atom)  (RSS)  (HTML)  (RSS)  (API) (API)
       │      │      │      │      │      │      │     │
       └──────┴──────┴──────┴──────┴──────┴──────┴─────┘
                           │
                           │ articles[]
                           │
                 ② 중복 필터링
                           │
     ┌─────────────────────▼─────────────────────┐
     │                   db.py                   │
     │             is_duplicate(url)             │
     └─────────────────────┬─────────────────────┘
                           │ 신규 기사 (또는 분석 누락 기사 보완)
                           │
                 ③ LLM 번역 · 분류
                           │
     ┌─────────────────────▼─────────────────────┐
     │              llm/analyzer.py              │
     │   translate_article_to_korean()           │
     │   classify()                              │
     │            (Gemini 2.5 Flash)             │
     └─────────────────────┬─────────────────────┘
                           │
                 ④ DB 저장
                           │
     ┌─────────────────────▼─────────────────────┐
     │                   db.py                   │
     │     save_article() / save_analysis()      │
     │                  news.db                  │
     └───────────────────────────────────────────┘
```

### 크롤러별 동작 방식

| 소스 | 방식 | 수집 기준 | 기본 카테고리 |
|------|------|-----------|:-------------:|
| 네이버뉴스 | HTML 파싱 | IT/과학, 경제, 국제 섹션별 최대 5건 | `IT`/`경제`/`국제` |
| Google News | RSS 파싱 | 글로벌 경제 및 AI/LLM 검색 피드별 최신 10건 | `경제`/`AI` |
| GeekNews | Atom/RSS 파싱 | 긱뉴스 최신 기술/AI 토픽 최대 10건 | `AI` |
| Reddit AI | RSS 파싱 | `r/LocalLLaMA`, `r/singularity` 핫 토픽 최대 10건 | `AI` |
| GitHub Trending | HTML 파싱 | 일간 트렌딩 AI/LLM/Agent 오픈소스 저장소 최대 10건 | `AI` |
| Hugging Face | RSS/HTML 파싱 | 공식 블로그 피드 및 Daily Papers 최신 10건 | `AI` |
| arXiv | Atom API 파싱 | 지정 AI/CS 논문 메타데이터 및 초록 | `AI` |
| dev.to | JSON API 파싱 | `ai` 태그 인기 기술 아티클 최신 10건 | `AI` |

### LLM 분석 내용

- **번역**: 해외 영문 기사(`translate_to_korean: True`)의 제목과 본문을 한국어로 번역
- **본문 보존**: 기사별 AI 요약은 생성하지 않으며 수집 본문(해외 기사 번역본 포함)을 제공합니다.
- **대분류**: `AI` / `IT` / `경제` / `국제`
- **중분류**: 세부 주제 (예: LLM, 오픈소스, 반도체, 거시경제)
- **태그**: 키워드 최대 10개

### DB 스키마 (`articles` 및 `article_analysis` 테이블)

- **`articles` 테이블**: `id`, `url`(UNIQUE), `source`, `title`, `content`, `published_at`, `crawled_at`, `summary`, `major_category`, `sub_category`, `tags`
- **`article_analysis` 테이블**: `id`, `article_id`(UNIQUE FK), `summary`, `major_category`, `sub_category`, `tags`(JSON 배열), `analyzed_at`

---

## 설치

```bash
# 1. 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 2. 의존성 설치
pip install -r requirements.txt
```

### 의존성

| 패키지 | 용도 |
|--------|------|
| `httpx` | HTTP 요청 |
| `beautifulsoup4` + `lxml` | HTML/XML 파싱 |
| `trafilatura` | 웹페이지 기사 본문 정밀 추출 |
| `APScheduler` | 정기 스케줄 실행 |
| `google-genai` | Gemini API 클라이언트 |

---

## 설정

### 필수: Gemini API 키

[Google AI Studio](https://aistudio.google.com)에서 발급 후 환경 변수로 설정합니다.

```powershell
# Windows PowerShell (세션 한정)
$env:GEMINI_API_KEY = "your-api-key-here"

# 영구 설정
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-api-key-here", "User")
```

### 선택: `config.py` 수정

```python
SCHEDULE_HOUR   = 8     # 스케줄러 실행 시각 (시)
SCHEDULE_MINUTE = 0     # 스케줄러 실행 시각 (분)
GEMINI_MODEL    = "gemini-2.5-flash"   # 사용할 Gemini 모델
REQUEST_TIMEOUT = 10    # HTTP 요청 타임아웃 (초)
```

---

## 사용법

### 1회 즉시 실행

```bash
python main.py --run
```

실행 흐름이 콘솔과 `pipeline.log`에 출력됩니다.

```
2026-05-14 08:00:00 [INFO] __main__: === 파이프라인 시작 ===
2026-05-14 08:00:05 [INFO] __main__: 총 35건 수집 완료
2026-05-14 08:00:06 [INFO] __main__: 분석 중: 삼성전자 2분기 실적 발표...
...
2026-05-14 08:01:30 [INFO] __main__: === 파이프라인 완료 | 수집: 35 | 중복: 5 | 저장: 30 ===
```

### 매일 자동 실행 (스케줄러)

```bash
python main.py --schedule
```

`config.py`의 `SCHEDULE_HOUR`/`SCHEDULE_MINUTE` 시각에 매일 자동 실행됩니다. 종료는 `Ctrl+C`.

### 크롤러만 단독 테스트 (API 키 없이)

```bash
python -c "from crawlers import get_all_articles; arts = get_all_articles(); print(f'{len(arts)}건 수집')"
```

---

## DB 확인

### Python으로 조회

```python
import sqlite3, json

conn = sqlite3.connect("news.db")
conn.row_factory = sqlite3.Row

# 최근 10건 조회
rows = conn.execute("""
    SELECT id, source, title, major_category, sub_category, crawled_at
    FROM articles
    ORDER BY id DESC
    LIMIT 10
""").fetchall()

for r in rows:
    print(dict(r))

conn.close()
```

### SQLite CLI

```bash
sqlite3 news.db
```
```sql
.headers on
.mode column

-- 전체 건수
SELECT COUNT(*) FROM articles;

-- 언론사별 건수
SELECT source, COUNT(*) FROM articles GROUP BY source;

-- 최근 기사 조회
SELECT id, source, title, major_category FROM articles ORDER BY id DESC LIMIT 10;

-- 태그 포함 조회
SELECT title, tags FROM articles WHERE major_category = 'IT' LIMIT 5;

.quit
```

### GUI 툴

- **DB Browser for SQLite**: https://sqlitebrowser.org (무료)
- **VS Code 확장**: `SQLite Viewer` 설치 후 `news.db` 파일 직접 열기
