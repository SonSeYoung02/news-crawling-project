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

- **카테고리 필터** — 경제 / IT / 기타
- **출처 필터** — 네이버뉴스 / 조선일보 / 한겨레 / Google News / arXiv / dev.to
- **키워드 검색** — 제목 및 본문 대상 (Enter 또는 검색 버튼)
- **기사 상세 보기** — AI 요약, 본문 전문, 태그, 원문 링크
- **페이지네이션** — 페이지당 20건

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
| API | FastAPI `http://localhost:8000` |

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
- API의 CORS는 `localhost:5173`만 허용합니다. 포트가 바뀌면 백엔드 `main.py`의 `allow_origins`를 함께 수정하세요.
