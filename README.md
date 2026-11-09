# AI 뉴스 수집 · 분석 및 큐레이션 뷰어 (News Crawling & Viewer)

국내외 주요 IT·경제·국제 뉴스와 글로벌 **AI 1차 원천 소스**(GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to, Google News, 네이버뉴스)를 자동 수집하고, **Google Gemini AI(`gemini-2.5-flash`)**로 한국어 번역·핵심 요약·카테고리 분류를 수행하여 웹 뷰어로 제공하는 통합 파이프라인 프로젝트입니다.

---

## 목차

- [1. 프로젝트 개요 및 핵심 기능](#1-프로젝트-개요-및-핵심-기능)
- [2. 사용 기술 스택 (Tech Stack)](#2-사용-기술-스택-tech-stack)
- [3. 시스템 아키텍처 및 데이터 흐름](#3-시스템-아키텍처-및-데이터-흐름)
- [4. 프로젝트 전체 구조](#4-프로젝트-전체-구조)
- [5. 수집 뉴스 소스 및 AI 분석 명세](#5-수집-뉴스-소스-및-ai-분석-명세)
- [6. 데이터베이스 및 API 명세](#6-데이터베이스-및-api-명세)
- [7. 시작하기 (설치 및 실행 방법)](#7-시작하기-설치-및-실행-방법)

---

## 1. 프로젝트 개요 및 핵심 기능

- **AI 1차 원천 중심 멀티 소스 크롤링**: 일반 가십성 뉴스(정치·사회·연예)를 배제하고, AI·개발 커뮤니티와 논문·오픈소스 트렌드 등 **8개 핵심 채널**에서 최신 정보를 수집합니다.
- **Gemini AI 기반 자동 번역·요약·분류**:
  - **영한 자동 번역**: 해외 소스(Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to, Google News)의 영문 제목과 본문을 자연스러운 한국어로 번역합니다.
  - **핵심 요약**: 긴 기사 본문을 한국어 **3~5문장**으로 요약합니다.
  - **자동 분류 및 태깅**: 기사를 대분류(`AI`, `IT`, `경제`, `국제`)와 세부 중분류로 나누고 핵심 키워드 태그(최대 10개)를 추출합니다.
- **중복 방지 및 분석 보완**: URL 기준 중복 수집을 차단하여 불필요한 LLM API 호출을 방지하며, 기존 수집 기사 중 AI 분석이 누락된 항목은 자동으로 재분석합니다.
- **직관적인 3단 웹 뷰어**: 출처별 사이드바 필터, 대분류 카테고리 탭, 키워드 검색, 페이지네이션, AI 요약본 및 원문 상세보기를 단일 화면(SPA)에서 제공합니다.

---

## 2. 사용 기술 스택 (Tech Stack)

### Data Collection & AI Pipeline (`news-crawling/`)

| 구분 | 기술 / 라이브러리 | 버전 / 모델 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **Language** | Python | 3.11+ | 크롤러 및 LLM 분석 파이프라인 전반 |
| **LLM / AI** | `google-genai` | `gemini-2.5-flash` | 영문 기사 한국어 번역, 3~5문장 요약, 대·중분류 및 태그 추출 |
| **HTTP Client** | `httpx` | `>=0.27.0` | 비동기/동기 HTTP 요청, 리다이렉트 추적, 타임아웃 및 헤더 제어 |
| **HTML / XML Parser** | `beautifulsoup4`, `lxml` | `>=4.12.0`, `>=5.0.0` | HTML DOM 파싱 및 RSS/Atom XML 피드 파싱 |
| **Article Extractor** | `trafilatura` | `>=1.12.0` | 뉴스 웹페이지 내 본문 텍스트 정밀 추출 |
| **Scheduler** | `APScheduler` | `>=3.10.0` | 매일 지정 시각(`Asia/Seoul` 08:00) 정기 크롤링 스케줄링 |

### Backend & Database (`news-viewer/backend/`)

| 구분 | 기술 / 라이브러리 | 버전 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **API Framework** | `FastAPI` | `>=0.115.0` | 기사 목록·상세·카테고리·출처 조회 REST API 및 Swagger(`/docs`) 제공 |
| **ASGI Server** | `uvicorn` | `>=0.30.0` | FastAPI 애플리케이션 서버 구동 |
| **Validation** | `Pydantic` | v2 | API 응답 스키마(`Article`, `ArticleListResponse` 등) 모델링 |
| **Database** | `SQLite3` | Built-in | `news-crawling/news.db` 단일 파일 영속화 (`articles`, `article_analysis`) |

### Frontend (`news-viewer/frontend/`)

| 구분 | 기술 / 라이브러리 | 버전 | 주요 활용 내용 |
| :--- | :--- | :--- | :--- |
| **UI Library** | `React`, `React DOM` | `^18.3.1` | 컴포넌트 기반 SPA UI, 상태 관리(`useState`, `useEffect`) |
| **Build Tool** | `Vite`, `@vitejs/plugin-react` | `^8.0.12`, `^4.3.4` | 개발 서버(HMR) 구동 및 프로덕션 번들 빌드 |
| **Styling** | Inline Styles (`s` 객체) + CSS | - | 외부 CSS 라이브러리 의존성 없는 경량 3단 레이아웃 스타일링 |

---

## 3. 시스템 아키텍처 및 데이터 흐름

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                        1. 수집 파이프라인 (news-crawling)                    │
│                                                                            │
│  [국내/글로벌 8대 소스]                                                     │
│   ├─ 네이버뉴스 (HTML)       ├─ GitHub Trending (HTML)                     │
│   ├─ Google News (RSS)       ├─ Hugging Face (RSS / HTML)                  │
│   ├─ GeekNews (Atom/RSS)     ├─ arXiv (Atom API)                           │
│   └─ Reddit AI (RSS)         └─ dev.to (JSON API)                          │
│               │                                                            │
│               ▼                                                            │
│     URL 중복 검사 (db.py) ──(기존 기사 & 분석 누락 시)──► 보완 분석 수행     │
│               │ (신규 기사)                                                │
│               ▼                                                            │
│     Gemini 2.5 Flash 분석 (llm/analyzer.py)                                │
│      ① 영문 기사 한국어 번역 (translate_article_to_korean)                 │
│      ② 한국어 3~5문장 핵심 요약 (summarize)                                │
│      ③ 대분류(AI/IT/경제/국제)·중분류·태그 분류 (classify)                 │
└───────────────┬────────────────────────────────────────────────────────────┘
                │
                ▼  SQLite 저장
┌────────────────────────────────────────────────────────────────────────────┐
│                   2. 공유 데이터베이스 (news-crawling/news.db)              │
│           [ articles 테이블 ]  ◄──── JOIN ────►  [ article_analysis 테이블 ]│
└───────────────┬────────────────────────────────────────────────────────────┘
                │
                ▼  SQL 조회 (COALESCE 조인)
┌────────────────────────────────────────────────────────────────────────────┐
│                     3. 백엔드 API 서버 (news-viewer/backend)                │
│        FastAPI (:8000) ── GET /articles, /categories, /sources             │
└───────────────┬────────────────────────────────────────────────────────────┘
                │
                ▼  REST API (JSON)
┌────────────────────────────────────────────────────────────────────────────┐
│                    4. 프론트엔드 웹 뷰어 (news-viewer/frontend)             │
│        React 18 + Vite (:5173) ── 출처·카테고리 필터 / 검색 / 상세 뷰       │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 프로젝트 전체 구조

```text
news-crawling-project/
├── news-crawling/                  # [Python 뉴스 크롤링 & Gemini 분석 파이프라인]
│   ├── crawlers/                   # 소스별 수집 어댑터 (표준 fetch() 인터페이스)
│   │   ├── __init__.py             # 8개 수집 소스 통합 호출 (get_all_articles)
│   │   ├── _rss.py                 # RSS 공통 파서 및 본문 추출 유틸리티
│   │   ├── naver.py                # 네이버뉴스 (IT/과학, 경제, 국제 섹션)
│   │   ├── google_news.py          # Google News (글로벌 경제 및 AI 검색 RSS)
│   │   ├── geeknews.py             # GeekNews (기술/AI 트렌드 Atom/RSS)
│   │   ├── reddit_ai.py            # Reddit AI (r/LocalLLaMA, r/singularity RSS)
│   │   ├── github_trending.py      # GitHub Trending (AI/LLM 트렌딩 오픈소스)
│   │   ├── huggingface.py          # Hugging Face (공식 블로그 RSS 및 Daily Papers)
│   │   ├── arxiv.py                # arXiv (최신 AI/CS 논문 Atom API)
│   │   └── devto.py                # dev.to (AI 태그 인기 글 JSON API)
│   ├── llm/
│   │   ├── __init__.py
│   │   └── analyzer.py             # Gemini API 클라이언트 (번역·요약·분류, 재시도 로직)
│   ├── config.py                   # 환경 변수(.env), 모델명, 카테고리, 타임아웃 설정
│   ├── db.py                       # SQLite 테이블 초기화 및 기사·분석 결과 CRUD
│   ├── main.py                     # CLI 진입점 (--run 즉시 실행 / --schedule 정기 실행)
│   ├── requirements.txt            # 크롤러 Python 패키지 의존성
│   └── README.md                   # 크롤링 파이프라인 상세 문서
│
├── news-viewer/                    # [풀스택 뉴스 큐레이션 웹 뷰어]
│   ├── backend/                    # FastAPI REST API 서버
│   │   ├── main.py                 # API 엔드포인트 정의 및 SQLite 연동
│   │   ├── requirements.txt        # 백엔드 Python 패키지 의존성
│   │   └── README.md               # 백엔드 API 상세 문서
│   └── frontend/                   # React 18 + Vite 프론트엔드 SPA
│       ├── public/                 # 정적 에셋 (favicon.svg, icons.svg)
│       ├── src/
│       │   ├── App.jsx             # 메인 뉴스 뷰어 UI (필터, 검색, 목록, 상세 패널)
│       │   ├── main.jsx            # React DOM 마운트 진입점
│       │   └── index.css           # 글로벌 스타일 리셋
│       ├── index.html              # HTML 엔트리포인트
│       ├── package.json            # 프론트엔드 의존성 및 스크립트
│       ├── vite.config.js          # Vite 번들러 설정
│       └── README.md               # 프론트엔드 상세 문서
│
├── .github/                        # GitHub 이슈 및 PR 템플릿
│   ├── ISSUE_TEMPLATE/             # feature.yml, task.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── start.ps1                       # Windows 원클릭 통합 실행 스크립트
└── README.md                       # 프로젝트 메인 문서
```

---

## 5. 수집 뉴스 소스 및 AI 분석 명세

### 5.1 수집 소스 (8종)

| 출처명 (`source`) | 수집 방식 | 수집 대상 및 특징 | 기본 대분류 | 한국어 번역 |
| :--- | :--- | :--- | :---: | :---: |
| **네이버뉴스** | HTML 파싱 | IT/과학(`105`), 경제(`101`), 국제(`001`) 섹션별 최신 기사 | 섹션별(`IT`/`경제`/`국제`) | X (원문 한국어) |
| **Google News** | RSS + 본문 추출 | 글로벌 경제 및 `artificial intelligence / LLM / generative AI` 쿼리 | `경제` / `AI` | O |
| **GeekNews** | Atom / RSS 파싱 | 긱뉴스 최신 개발·기술·AI 토픽 요약본 | `AI` | X (원문 한국어) |
| **Reddit AI** | RSS 파싱 | `r/LocalLLaMA`, `r/singularity` 서브레딧 상위 화제 글 | `AI` | O |
| **GitHub Trending** | HTML 파싱 | 일간 트렌딩 저장소 중 AI/LLM/Agent 관련 오픈소스 프로젝트 | `AI` | O |
| **Hugging Face** | RSS / HTML 파싱 | Hugging Face 공식 블로그 및 Daily Papers 최신 모델·논문 소식 | `AI` | O |
| **arXiv** | Atom API | Computer Science / AI 분야 논문 초록(Abstract) 및 메타데이터 | `AI` | O |
| **dev.to** | REST JSON API | `ai` 태그 인기 기술 아티클 및 본문 | `AI` | O |

### 5.2 Gemini LLM 분석 항목 (`llm/analyzer.py`)

- **모델**: `gemini-2.5-flash` (최대 3회 지수 백오프 재시도 적용)
- **번역 (`translate_article_to_korean`)**: 영문 기사의 제목과 본문을 한국어로 번역하여 JSON으로 반환합니다.
- **요약 (`summarize`)**: 기사 본문(최대 3,000자)을 바탕으로 핵심 내용을 한국어 3~5문장으로 요약합니다.
- **분류 (`classify`)**:
  - **대분류 (`major_category`)**: `AI`, `IT`, `경제`, `국제` (분류 실패 시 크롤러의 기본 카테고리로 폴백)
  - **중분류 (`sub_category`)**: 세부 주제 (예: `LLM`, `오픈소스`, `반도체`, `거시경제` 등)
  - **태그 (`tags`)**: 핵심 키워드 배열 (최대 10개)

---

## 6. 데이터베이스 및 API 명세

### 6.1 SQLite 스키마 (`news-crawling/news.db`)

- **`articles` 테이블**: 수집된 기사 원문(또는 번역본), URL(UNIQUE), 출처, 발행일, 수집 시각 저장
- **`article_analysis` 테이블**: `article_id`(FK, UNIQUE) 기준 요약(`summary`), 대분류(`major_category`), 중분류(`sub_category`), 태그(`tags` JSON 배열), 분석 시각(`analyzed_at`) 저장

### 6.2 백엔드 REST API (`http://localhost:8000`)

| 메서드 | 엔드포인트 | 설명 | 주요 쿼리 파라미터 |
| :---: | :--- | :--- | :--- |
| `GET` | `/articles` | 기사 목록 조회 (최신순, 페이지네이션 및 필터) | `page`(기본 1), `size`(기본 20), `category`, `source`, `q`(검색어) |
| `GET` | `/articles/{article_id}` | 특정 기사 상세 정보 조회 | - |
| `GET` | `/categories` | 대분류 카테고리별 기사 수 집계 조회 | - |
| `GET` | `/sources` | 출처(언론사/플랫폼)별 기사 수 집계 조회 | - |
| `GET` | `/docs` | Swagger UI 인터랙티브 API 문서 | - |

---

## 7. 시작하기 (설치 및 실행 방법)

### 7.1 사전 요구사항

- **Python** 3.11 이상
- **Node.js** 18 이상 및 `npm`
- **Google Gemini API Key** ([Google AI Studio](https://aistudio.google.com)에서 발급)

### 7.2 환경 변수 설정

`news-crawling/.env` 파일을 생성하거나 시스템 환경 변수로 `GEMINI_API_KEY`를 설정합니다.

```env
# news-crawling/.env
GEMINI_API_KEY=your-gemini-api-key-here
```

### 7.3 의존성 설치

```powershell
# 1. 크롤러 의존성 설치
cd news-crawling
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. 백엔드 의존성 설치
cd ..\news-viewer\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. 프론트엔드 의존성 설치
cd ..\frontend
npm install
```

### 7.4 실행 방법

#### 방법 A: Windows 통합 실행 스크립트 (`start.ps1`) 사용 (권장)

저장소 루트에서 아래 명령어로 백엔드(`:8000`)와 프론트엔드(`:5173`)를 한 번에 실행할 수 있습니다.

```powershell
# 뷰어(백엔드 + 프론트엔드) 실행
.\start.ps1

# 뉴스 크롤링 1회 실행과 함께 뷰어 시작
.\start.ps1 -Crawl
```

#### 방법 B: 개별 수동 실행

```powershell
# 1) 뉴스 수집 및 AI 분석 실행 (news-crawling/)
cd news-crawling
python main.py --run        # 1회 즉시 수집 및 분석
python main.py --schedule   # 매일 08:00 자동 수집 스케줄러 구동

# 2) 백엔드 API 서버 실행 (news-viewer/backend/)
cd news-viewer/backend
uvicorn main:app --reload   # http://localhost:8000

# 3) 프론트엔드 개발 서버 실행 (news-viewer/frontend/)
cd news-viewer/frontend
npm run dev                 # http://localhost:5173
```
