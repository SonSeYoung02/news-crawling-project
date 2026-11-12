# AI·IT 뉴스 크롤링 + Gemini 순차 번역 파이프라인

네이버뉴스, Google News, GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to에서 최신 뉴스를 수집하여 원문 그대로 SQLite에 우선 저장하고, 매일 새벽 시간대(01:00~06:00 KST)에 Google Gemini API 무료 티어를 통해 영문 기사의 제목과 본문을 한국어로 순차 번역하는 파이프라인입니다.

---

## 목차

- [구조](#구조)
- [새벽 수집 및 번역 파이프라인 동작 로직](#새벽-수집-및-번역-파이프라인-동작-로직)
- [설정 및 무료 티어 가이드](#설정-및-무료-티어-가이드)
- [사용법](#사용법)
- [데이터베이스 명세](#데이터베이스-명세)

---

## 구조

```
news-crawling/
├── main.py                  # 진입점 (CLI: --run / --schedule)
├── config.py                # 환경 설정 (API 키, DB 경로, 스케줄, 무료 한도 등)
├── db.py                    # SQLite 스키마 초기화 및 CRUD 로직
├── crawlers/                # 뉴스 수집 어댑터
│   ├── __init__.py          # 전체 소스 통합 (get_all_articles)
│   ├── naver.py             # 네이버뉴스 크롤러 (HTML 파싱)
│   ├── google_news.py       # Google News 글로벌 크롤러 (RSS + trafilatura)
│   ├── geeknews.py          # GeekNews 크롤러 (Atom/RSS)
│   ├── reddit_ai.py         # Reddit AI 서브레딧 크롤러 (RSS)
│   ├── github_trending.py   # GitHub Trending 오픈소스 크롤러 (HTML)
│   ├── huggingface.py       # Hugging Face 블로그/논문 크롤러 (RSS/HTML)
│   ├── arxiv.py             # arXiv API 크롤러
│   ├── devto.py             # dev.to API 크롤러
│   └── _rss.py              # RSS 공통 파서
├── translation/             # 번역 파이프라인 모듈
│   ├── __init__.py
│   ├── queue.py             # 신규 우선 번역 대기열 생성 및 정렬
│   ├── chunker.py           # 긴 본문 문단/문장 단위 분할
│   ├── translator.py        # Gemini API 호출 및 조각별 재개(Resume)
│   └── rate_limiter.py      # RPM/일일 쿼터 통제 및 05:55 마감 제어
├── news.db                  # SQLite DB 파일
├── pipeline.log             # 실행 로그 파일
└── requirements.txt         # 파이썬 의존성
```

---

## 새벽 수집 및 번역 파이프라인 동작 로직

1. **원문 수집 및 DB 즉시 저장 (01:00 KST)**:
   - 8개 소스에서 기사를 수집하여 원문 그대로 `articles` 테이블에 우선 저장합니다.
   - 이미 저장된 기사는 출처의 최신 정보로 갱신하며, 요약(`summarize`)이나 분류(`classify`) 호출은 전면 배제합니다.
2. **번역 대기열 큐 생성 및 정렬**:
   - 한국어 소스(네이버, GeekNews)는 번역 대상에서 제외합니다.
   - **우선순위 1**: 당일 새로 수집된 신규 영어 기사.
   - **우선순위 2**: 이전 실행의 미번역 영어 기사 및 원문 변경 기사.
   - 각 그룹 내에서는 정규화된 발행시각 내림차순, 수집시각 내림차순, ID 오름차순으로 정렬합니다.
3. **Gemini 순차 번역 및 조각별 저장 (01:00 ~ 05:55)**:
   - 무료 API 한도(RPM, 일일 한도)를 준수하며 요청 간 간격을 제어합니다.
   - 긴 기사는 문단 단위로 분할하여 개별 조각(chunk)을 번역 즉시 `translation_chunks`에 저장합니다.
   - 한도 소진이나 네트워크 중단 시 다음 날 완료된 조각은 재호출 없이 미완료 조각부터 안전하게 이어받습니다.
   - 제목과 모든 본문 조각이 완료된 후에만 `article_translations` 레코드를 `completed`로 전환합니다.
4. **마감 시간 통제 (05:55 ~ 06:00)**:
   - 매일 05:55 KST 이후에는 새로운 번역 요청을 시작하지 않습니다.
   - 진행 중인 트랜잭션을 정리하고 06:00 이전에 프로세스를 정상 종료합니다.

---

## 설정 및 무료 티어 가이드

`config.py` 또는 `.env` 파일을 통해 설정을 관리합니다.

```env
# Google Gemini API 키 (필수)
GEMINI_API_KEY="your-api-key-here"

# 무료 티어 모델 후보 설정
GEMINI_MODEL="gemini-2.5-flash"
REQUIRE_FREE_TIER=true

# 무료 한도 통제 설정
GEMINI_RPM_LIMIT=10
GEMINI_DAILY_LIMIT=1000
REQUEST_INTERVAL_SECONDS=6.0

# 새벽 스케줄 및 마감 시간 설정 (KST 기준)
SCHEDULE_HOUR=1
SCHEDULE_MINUTE=0
CUTOFF_HOUR=5
CUTOFF_MINUTE=55
DEADLINE_HOUR=6
DEADLINE_MINUTE=0
```

> **주의**: Google AI Studio에서 무료 티어로 발급된 API 키와 프로젝트를 사용하십시오. 유료 결제 계정이 연결된 프로젝트는 자동 과금이 발생할 수 있으므로 주의해야 합니다.

---

## 사용법

```bash
# 1회 즉시 실행 (수집 및 순차 번역)
python main.py --run

# 새벽 01:00 KST 자동 스케줄러 실행
python main.py --schedule
```

---

## 데이터베이스 명세

- `articles`: 수집 원문 보존
- `article_translations`: 한국어 번역문 및 상태 (`pending`, `in_progress`, `completed`, `failed`)
- `translation_chunks`: 긴 본문의 분할 조각 번역문 및 조각별 완료 상태
- `translation_quota`: 일일 호출량 및 토큰 수 영속화
- `crawl_locks`: 단일 프로세스 실행 락
- `article_analysis`: 이전 분석 데이터 보존용
