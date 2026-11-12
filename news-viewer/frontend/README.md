# 뉴스 뷰어 — Frontend

크롤링된 한국 신문 기사를 브라우저에서 탐색하는 React SPA입니다.  
FastAPI 백엔드(`news-viewer/backend`)가 제공하는 REST API를 소비합니다.

## 시작하기

```bash
npm install
npm run dev
```

브라우저에서 http://localhost:5173 접속. **백엔드 서버가 먼저 실행되어 있어야 합니다.**

### 백엔드 실행 (별도 터미널)

```bash
cd ../backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## 주요 기능

- **카테고리 필터** — API가 반환하는 카테고리와 건수 표시
- **출처 필터** — 네이버뉴스 / Google News / GeekNews / Reddit AI / GitHub Trending / Hugging Face / arXiv / dev.to
- **키워드 검색** — 제목 및 본문 대상 (Enter 또는 검색 버튼)
- **기사 상세 보기** — 한국어 번역문/원문 본문(Markdown 서식 지원), LLM 요약(있는 경우), 태그, 원문 링크
- **페이지네이션** — 페이지당 20건
- **반응형 화면** — 1,024px 이상은 3단 구성, 작은 화면은 접이식 필터와 기사 목록·상세 전환

## 휴대폰에서 접속하기

1. PC와 휴대폰을 같은 Wi-Fi에 연결하고 PC에서 백엔드와 `npm run dev`를 실행합니다.
2. PC의 내부 IPv4 주소를 확인하고 휴대폰에서 `http://<PC의 내부 IP>:5173`에 접속합니다. 휴대폰의 `localhost`는 PC를 가리키지 않습니다.
3. Vite는 LAN 인터페이스에서 수신하며 `/api` 요청을 PC 내부의 `http://127.0.0.1:8000`으로 전달합니다. 백엔드를 외부 인터페이스에 노출할 필요가 없습니다.

호스트 방화벽 또는 공유기의 무선 기기 격리 설정이 접속을 막을 수 있습니다. 앱은 방화벽이나 공유기 설정을 자동 변경하지 않습니다. 개발 서버 포트가 사용 중이면 실행을 중단하므로 별도 worktree를 실행할 때는 `npm run dev -- --port 5180`처럼 지정하고 해당 포트로 접속합니다.

## 운영 배포의 API 연결

프론트엔드는 같은 출처의 `/api`를 호출합니다. 개발 서버와 `npm run preview`에는 프록시가 구성되어 있지만, `dist/`를 정적 호스팅할 때는 웹 서버에서 `/api/*`를 백엔드의 `/*`로 전달하는 리버스 프록시를 별도로 구성해야 합니다. `npm run preview`는 로컬 빌드 확인용이며 운영 서버로 사용하지 않습니다. Cloudflare Tunnel만 연결한다고 API 경로가 자동 구성되지는 않습니다.

## 빌드

```bash
npm run build    # dist/ 디렉토리에 프로덕션 번들 생성
npm run preview  # 프로덕션 빌드 로컬 미리보기
```

## 기술 스택

| 항목 | 내용 |
|------|------|
| 프레임워크 | React 18 |
| 번들러 | Vite 8 |
| 스타일 | 인라인 스타일 (CSS-in-JS 없음) |
| API | 같은 출처 `/api` → FastAPI `http://127.0.0.1:8000` |

## 프로젝트 구조

```
frontend/
├── index.html          # HTML 진입점 (#app 마운트)
├── vite.config.js      # Vite + React 플러그인 설정
├── src/
│   ├── main.jsx        # ReactDOM.createRoot 부트스트랩
│   ├── App.jsx         # 전체 앱 (상태, 데이터 패칭, UI)
│   └── index.css       # 전역 리셋 및 스크롤바 스타일
└── public/
    └── favicon.svg
```

## 참고

- `.npmrc`의 `legacy-peer-deps=true`는 Vite 8과 `@vitejs/plugin-react` 4.x 간 peer dependency 충돌 우회를 위한 설정입니다.
- 브라우저는 프론트와 같은 출처의 `/api`만 호출하므로 LAN 접속을 위해 백엔드 CORS 허용 목록을 넓힐 필요가 없습니다.

## 오늘의 AI 브리핑

첫 화면은 최근 24시간의 AI 소식 최대 5개를 보여줍니다. 주제·출처 다양성, 최신순을 반영한 규칙 기반 선정이며 조회 시각을 한국 시간으로 표시합니다.

- 사이드바의 `오늘의 AI 브리핑` / `전체 기사`로 보기를 전환합니다. 모바일에서는 `필터`를 열어 전환합니다.
- 검색·카테고리·출처 선택 시 기사 목록으로 자동 전환됩니다.
- 브리핑 기사 선택 시 3단 뷰어의 읽기 영역에서 본문(번역 완료 기사는 한국어 번역문 우선)과 상세 정보를 확인합니다.
- 로딩·최근 기사 없음·요청 실패를 구분하고 새로고침과 재시도를 제공합니다.
- 백엔드 #23의 `GET /briefing`과 연동하여 한국어 번역문/원문 기사 및 다양성 브리핑을 제공합니다.

기사 카드와 읽기 영역은 번역 파이프라인에서 제공하는 한국어 번역문과 본문(Markdown 서식 지원)을 자연스럽게 표시하며, LLM 요약이 있는 경우 요약 카드도 함께 제공합니다.
