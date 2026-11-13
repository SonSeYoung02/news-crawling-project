# AI 뉴스 수집 · 분석 및 큐레이션 뷰어 (News Crawling & Viewer)

국내외 주요 IT·경제·국제 뉴스와 글로벌 **AI 1차 원천 소스**(GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to, Google News, 네이버뉴스)를 매일 새벽 자동 수집하고, **Google Gemini AI** 무료 티어를 통해 영문 기사의 제목과 본문을 한국어로 순차 번역하여 아침 시간대에 웹 뷰어로 편리하게 열람할 수 있도록 제공하는 통합 파이프라인 프로젝트입니다.

---

## 목차

- [1. 프로젝트 개요 및 핵심 기능](#1-프로젝트-개요-및-핵심-기능)
- [2. 사용 기술 스택 (Tech Stack)](#2-사용-기술-스택-tech-stack)
- [3. 시스템 아키텍처 및 데이터 흐름](#3-시스템-아키텍처-및-데이터-흐름)
- [4. 프로젝트 전체 구조](#4-프로젝트-전체-구조)
- [5. 수집 뉴스 소스 및 새벽 번역 파이프라인 명세](#5-수집-뉴스-소스-및-새벽-번역-파이프라인-명세)
- [6. 데이터베이스 스키마 및 API 계약](#6-데이터베이스-스키마-및-api-계약)
- [7. 시작하기 (설치 및 실행 방법)](#7-시작하기-설치-및-실행-방법)

---

## 1. 프로젝트 개요 및 핵심 기능

- **AI 1차 원천 중심 멀티 소스 크롤링**: 일반 가십성 뉴스(정치·사회·연예)를 배제하고, AI·개발 커뮤니티와 논문·오픈소스 트렌드 등 **8개 핵심 채널**에서 최신 원문 정보를 수집하여 즉시 보존합니다.
- **새벽 01:00 KST 배치 및 Gemini 무료 순차 번역**:
  - **새벽 1회 실행 스케줄**: 매일 한국 시간(`Asia/Seoul`) **01:00**에 수집을 시작하고, **05:55** 이후 신규 요청을 중단하며 **06:00 전**에 프로세스를 정상 종료합니다.
  - **무료 티어 번역 집중 투입**: 한정된 무료 API 예산을 가장 가치 있는 곳에 사용하기 위해 요약(`summarize`)과 AI 분류(`classify`) 호출을 전면 배제하고, 모든 무료 쿼터를 **영어 기사 한국어 번역**에만 집중 투입합니다.
  - **신규 기사 최우선 정렬**: 당일 새로 수집된 최신 기사를 최우선으로 번역하고, 이전 실행의 미번역 기사는 남은 시간과 무료 한도 범위 내에서 후순위로 처리합니다.
  - **긴 본문 문단 분할(Chunking) 및 재개(Resume)**: 긴 기사는 문단 단위로 분할하여 번역 즉시 영속화하며, 중단 시 이미 번역된 조각은 재호출하지 않고 미완료 조각부터 안전하게 이어받습니다.
  - **일일 예산 영속화 및 프로세스 락**: SQLite에 일일 호출량을 영속화하여 재시작에도 무료 한도를 초과하지 않으며, 단일 프로세스 락으로 중복 실행을 방지합니다.
- **한국어 우선 웹 뷰어 및 하위 호환성**:
  - 백엔드 API는 번역이 완료된 기사의 경우 한국어 번역문을 기본 `title`, `content`로 우선 제공하고, 미번역 기사는 원문으로 안전하게 폴백합니다.
  - 제목·본문·원문 검색 지원 및 기존 카테고리/태그/요약과의 100% 호환성을 보장합니다.
  - 한국어 출처(`네이버뉴스`, `GeekNews`) 기사는 번역 대상에서 제외되며, API는 `translation_status`를 `not_needed`로 반환합니다.
- **오늘의 AI 브리핑**: 첫 화면에서 최근 24시간의 AI 기사 최대 5개를 주제·출처 다양성과 최신순 기준으로 골라 보여줍니다(`GET /briefing`).
- **밝은 뉴스 리더 UI**: 밝은 중립 배경과 녹색 강조(`#258347`), 출처별 배지, 출처·날짜·제목·요약 위계를 갖춘 읽기 중심 화면입니다. PC는 3단 구성, 1,023px 이하에서는 접이식 필터와 목록·상세 전환을 제공하며 키보드 포커스를 표시합니다.

---

## 2. 사용 기술 스택 (Tech Stack)

### Data Collection & Translation Pipeline (`news-crawling/`)

| 구분 | 기술 / 라이브러리 | 버전 / 모델 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.11+ / 3.14 | 크롤러 및 번역 파이프라인 전반 |
| **LLM / AI** | `google-genai` | `gemini-2.5-flash` (무료 티어 후보) | 영문 기사 제목 및 본문 한국어 순차 번역 (무료 한도 준수) |
| **HTTP Client** | `httpx` | `>=0.27.0` | 비동기/동기 HTTP 요청, 리다이렉트 추적, 타임아웃 및 헤더 제어 |
| **HTML / XML Parser** | `beautifulsoup4`, `lxml` | `>=4.12.0`, `>=5.0.0` | HTML DOM 파싱 및 RSS/Atom XML 피드 파싱 |
| **Article Extractor** | `trafilatura` | `>=1.12.0` | 뉴스 웹페이지 내 본문 텍스트 정밀 추출 |
| **Scheduler** | `APScheduler` | `>=3.10.0` | 매일 새벽(`Asia/Seoul` 01:00) 정기 크롤링 및 번역 스케줄링 |

### Backend & Database (`news-viewer/backend/`)

| 구분 | 기술 / 라이브러리 | 버전 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **API Framework** | `FastAPI` | `>=0.115.0` | 기사 목록·상세·카테고리·출처 조회 REST API 및 Swagger(`/docs`) 제공 |
| **ASGI Server** | `uvicorn` | `>=0.30.0` | FastAPI 애플리케이션 서버 구동 |
| **Validation** | `Pydantic` | v2 | API 응답 스키마(`Article`, `ArticleListResponse` 등) 모델링 |
| **Database** | `SQLite3` | Built-in | `news-crawling/news.db` 영속화 (원문, 번역문, 분할 조각, 일일 쿼터, 락) |

### Frontend (`news-viewer/frontend/`)

| 구분 | 기술 / 라이브러리 | 버전 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **UI Library** | `React`, `React DOM` | `^18.3.1` | 컴포넌트 기반 SPA UI, 상태 관리(`useState`, `useEffect`) |
| **Build Tool** | `Vite`, `@vitejs/plugin-react` | `^8.0.12`, `^4.3.4` | 개발 서버(HMR) 구동 및 프로덕션 번들 빌드 |
| **Styling** | Inline Styles (`s` 객체) + CSS | - | 외부 CSS 라이브러리 의존성 없는 경량 3단 레이아웃 스타일링 |

---

## 3. 시스템 아키텍처 및 데이터 흐름

```
[다중 뉴스 소스 (8종)]
 (네이버, 긱뉴스, 구글뉴스, 레딧, 깃허브, 허깅페이스, arXiv, dev.to)
       │
       ▼ (매일 01:00 KST)
[news-crawling: main.py]
       │
       ├─ 1. 원문 수집 및 DB 즉시 저장 ───► [SQLite: articles]
       │                                         ▲
       ├─ 2. 번역 대기열 구성 (신규 우선)            │
       │                                         │
       ├─ 3. Gemini 무료 API 순차 번역 (01:00~05:55) │
       │     (문단 청크 저장, 한도/마감 제어)        │
       ▼                                         ▼
[SQLite: article_translations, chunks] ◄── 조인 / 폴백 조회
       ▲
       │ (REST API GET)
[news-viewer/backend (FastAPI)]
       │
       ▼ (HTTP/JSON)
[news-viewer/frontend (React)]
 (번역 완료 기사는 한국어 우선 표시, 미번역 기사는 원문 표시)
```

---

## 4. 프로젝트 전체 구조

```
news-crawling-project/
├── news-crawling/                  # [Python 뉴스 크롤링 & Gemini 번역 파이프라인]
│   ├── crawlers/                   # 소스별 수집 어댑터 (get_all_articles)
│   ├── translation/                # 번역 파이프라인 모듈
│   │   ├── __init__.py
│   │   ├── queue.py                # 신규 우선 번역 대기열 큐
│   │   ├── chunker.py              # 긴 본문 문단/문장 단위 분할기
│   │   ├── translator.py           # Gemini API 번역 및 부분 조각 재개(Resume)
│   │   └── rate_limiter.py         # 무료 한도(RPM/RPD) 및 05:55 마감 통제
│   ├── config.py                   # 환경 변수, 스케줄 시각(01:00), 무료 한도 설정
│   ├── db.py                       # SQLite 테이블 초기화, 원문/번역문/쿼터/락 CRUD
│   ├── main.py                     # CLI 진입점 (--run 즉시 실행 / --schedule 새벽 스케줄러)
│   ├── requirements.txt            # 크롤러 Python 패키지 의존성
│   └── README.md                   # 크롤링 파이프라인 상세 문서
│
├── news-viewer/                    # [풀스택 뉴스 큐레이션 웹 뷰어]
│   ├── backend/                    # FastAPI REST API 서버
│   │   ├── main.py                 # 번역문 우선 제공 API 엔드포인트
│   │   ├── requirements.txt        # 백엔드 Python 패키지 의존성
│   │   └── README.md               # 백엔드 API 상세 문서
│   └── frontend/                   # React 18 + Vite 프론트엔드 SPA
│
├── start.ps1                       # Windows 실행 스크립트
└── README.md                       # 프로젝트 메인 문서
```

---

## 5. 수집 뉴스 소스 및 새벽 번역 파이프라인 명세

### 5.1 수집 소스 (8종)

| 출처명 (`source`) | 수집 방식 | 수집 대상 및 특징 | 기본 대분류 | 한국어 번역 |
| :--- | :--- | :--- | :---: | :---: |
| **네이버뉴스** | HTML 파싱 | IT/과학(`105`), 경제(`101`), 국제(`001`) 섹션별 최신 기사 | 섹션별(`IT`/`경제`/`국제`) | X (원문 한국어) |
| **Google News** | RSS + 본문 추출 | 글로벌 경제 및 AI 검색 RSS | `경제` / `AI` | O (순차 번역) |
| **GeekNews** | Atom / RSS 파싱 | 긱뉴스 최신 개발·기술·AI 토픽 요약본 | `AI` | X (원문 한국어) |
| **Reddit AI** | RSS 파싱 | `r/LocalLLaMA`, `r/singularity` 서브레딧 상위 화제 글 | `AI` | O (순차 번역) |
| **GitHub Trending** | HTML 파싱 | 일간 트렌딩 저장소 중 AI/LLM 오픈소스 프로젝트 | `AI` | O (순차 번역) |
| **Hugging Face** | RSS / HTML 파싱 | Hugging Face 공식 블로그 및 Daily Papers | `AI` | O (순차 번역) |
| **arXiv** | Atom API | Computer Science / AI 분야 논문 초록 | `AI` | O (순차 번역) |
| **dev.to** | REST JSON API | `ai` 태그 인기 기술 아티클 및 본문 | `AI` | O (순차 번역) |

### 5.2 번역 운영 정책

1. **시간 정책**: 매일 01:00 KST 시작. 05:55 이후 신규 요청 시작 금지, 06:00 이전 안전 종료.
2. **무료 한도 준수**: 설정된 RPM(분당 요청 수) 및 일일 요청 수(RPD)를 초과하지 않으며, 일일 사용량을 SQLite에 영속화.
3. **우선순위**:
   - 1순위: 이번 실행에서 신규 수집된 영어 기사
   - 2순위: 이전 실행의 미완료 영어 기사 및 원문 갱신 기사
   - 정렬: 정규화된 발행시각 내림차순, 수집시각 내림차순, ID 오름차순
4. **부분 완료 재개(Resume)**: 긴 기사는 문단 단위 분할 후 조각별 저장. 중단 시 다음 날 완료된 조각은 재호출 없이 미완료 조각부터 이어받아 번역.

---

## 6. 데이터베이스 스키마 및 API 계약

### 6.1 공유 SQLite 스키마 (`news-crawling/news.db`)

- **`articles`**: 크롤링 수집 원문 보존 테이블
  - `id`, `url`(UNIQUE), `source`, `title`, `content`, `published_at`, `crawled_at`, `summary`, `major_category`, `sub_category`, `tags`
- **`article_translations`**: 기사별 한국어 번역문 테이블
  - `id`, `article_id`, `content_hash`, `translated_title`, `translated_content`, `language`('ko'), `status`('pending'|'in_progress'|'completed'|'failed'), `attempts`, `completed_at`, `model`, `last_error`, `created_at`, `updated_at`, `UNIQUE(article_id, content_hash)`
- **`translation_chunks`**: 긴 본문의 조각별 번역 영속화 테이블
  - `id`, `article_id`, `content_hash`, `chunk_index`, `total_chunks`, `original_chunk`, `translated_chunk`, `status`, `completed_at`, `UNIQUE(article_id, content_hash, chunk_index)`
- **`translation_quota`**: 일일 API 호출량 및 토큰 영속화 테이블
  - `id`, `date`(UNIQUE), `request_count`, `token_count`, `last_request_at`
- **`crawl_locks`**: 중복 실행 방지 프로세스 락 테이블
  - `name`(PK), `acquired_at`, `pid`, `info`
- **`article_analysis`**: 기존 LLM 분석 데이터 보존 테이블 (하위 호환)

### 6.2 백엔드 API 계약

- **`GET /articles` & `GET /articles/{id}`**:
  - `title`, `content`: 번역 완료(`status == 'completed'`) 시 한국어 번역문 우선 반환, 미완료 시 원문 반환.
  - `original_title`, `original_content`, `translated_title`, `translated_content`, `translation_status` 필드 추가 제공.
  - `translation_status`: 번역 레코드가 있으면 그 상태(`pending`|`in_progress`|`completed`|`failed`), 없으면 한국어 출처(`네이버뉴스`, `GeekNews`, 레거시 `naver`, `geeknews`)는 `not_needed`, 그 외는 `pending`.
  - `summary`, `major_category`, `sub_category`, `tags`: 기존 분석 데이터 호환 제공.
  - 검색 파라미터 `q`: 원문 제목, 번역 제목, 원문 본문, 번역 본문, 요약 동시 검색.
- **`GET /briefing`**:
  - 최근 24시간(발행시각, 없으면 수집시각 기준) 동안의 `major_category = 'AI'` 기사 중 최대 5개를 반환합니다.
  - 주제(`sub_category`)·출처 다양성을 우선하고 최신순으로 선정하며, 기사 필드는 `/articles`와 같은 번역 우선 규칙을 따릅니다.
  - 응답: `generated_at`, `window_start`, `window_end`, `selection_method`, `articles`.
