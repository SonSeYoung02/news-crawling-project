# 뉴스 뷰어 백엔드

FastAPI 기반의 뉴스 기사 조회 REST API 서버입니다.  
뉴스 크롤러(`news-crawling`)가 수집한 SQLite 데이터베이스를 읽어 프론트엔드에 데이터를 제공합니다.

---

## 프로젝트 구조

```
backend/
├── main.py           # FastAPI 애플리케이션 및 API 엔드포인트
├── requirements.txt  # Python 의존성
└── .gitignore
```

데이터베이스는 별도 경로에 위치합니다.

```
news-crawling-project/
├── crawling-python/
│   └── news.db       # 크롤러가 생성하는 SQLite DB
└── news-viewer/
    └── backend/      # 이 폴더
```

---

## 시작하기

### 1. 사전 요구사항

- Python 3.11 이상
- 뉴스 크롤러 실행 후 생성된 `news.db` 파일

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 서버 실행

```bash
uvicorn main:app --reload
```

서버가 실행되면 아래 주소에서 접근할 수 있습니다.

| 항목 | 주소 |
|------|------|
| API 서버 | `http://localhost:8000` |
| 자동 문서 (Swagger) | `http://localhost:8000/docs` |
| 자동 문서 (ReDoc) | `http://localhost:8000/redoc` |

---

## API 엔드포인트

### `GET /articles` — 기사 목록 조회

뉴스 기사 목록을 페이지네이션, 카테고리, 출처, 검색어 필터와 함께 반환합니다.

**쿼리 파라미터**

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `page` | int | 1 | 페이지 번호 (1 이상) |
| `size` | int | 20 | 페이지당 기사 수 (1~100) |
| `category` | string | - | 대분류 카테고리 필터 |
| `source` | string | - | 출처(언론사) 필터 |
| `q` | string | - | 제목 또는 요약 내 검색어 |

**응답 예시**

```json
{
  "total": 342,
  "page": 1,
  "size": 20,
  "articles": [
    {
      "id": 1,
      "title": "기사 제목",
      "summary": "기사 요약",
      "source": "언론사명",
      "major_category": "IT",
      "tags": ["AI", "기술"],
      "crawled_at": "2026-05-14T10:00:00"
    }
  ]
}
```

---

### `GET /articles/{article_id}` — 기사 단건 조회

특정 ID의 기사를 반환합니다. 존재하지 않으면 `404`를 반환합니다.

**응답 예시**

```json
{
  "id": 1,
  "title": "기사 제목",
  "summary": "기사 요약",
  "source": "언론사명",
  "major_category": "IT",
  "tags": ["AI", "기술"],
  "crawled_at": "2026-05-14T10:00:00"
}
```

---

### `GET /categories` — 카테고리 목록 조회

DB에 존재하는 카테고리와 각 기사 수를 반환합니다. 기사 수 내림차순으로 정렬됩니다.

**응답 예시**

```json
[
  { "major_category": "IT", "count": 120 },
  { "major_category": "경제", "count": 85 }
]
```

---

### `GET /sources` — 출처 목록 조회

DB에 존재하는 언론사와 각 기사 수를 반환합니다. 기사 수 내림차순으로 정렬됩니다.

**응답 예시**

```json
[
  { "source": "연합뉴스", "count": 200 },
  { "source": "조선일보", "count": 142 }
]
```

---

## 코드 로직 설명

### DB 연결 — `_connect()`

```python
@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

`contextmanager`를 사용해 `with` 블록이 끝나면 자동으로 DB 연결을 닫습니다.  
`sqlite3.Row`를 `row_factory`로 설정하면 쿼리 결과를 컬럼명으로 접근할 수 있습니다.

---

### 태그 변환 — `_row_to_dict()`

```python
def _row_to_dict(row) -> dict:
    d = dict(row)
    if isinstance(d.get("tags"), str):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    return d
```

SQLite에는 배열 타입이 없기 때문에 태그는 JSON 문자열(`"[\"AI\", \"기술\"]"`)로 저장됩니다.  
이 함수가 응답 직전에 파이썬 리스트로 파싱합니다. 파싱 실패 시 빈 리스트를 반환합니다.

---

### 기사 목록 — `GET /articles`

1. `page`와 `size`로 `OFFSET`, `LIMIT`을 계산합니다.
2. `category`, `source`, `q` 파라미터가 있으면 `WHERE` 절 조건을 동적으로 조립합니다.
3. 전체 건수(`COUNT(*)`)와 실제 데이터를 같은 DB 연결 안에서 조회해 반환합니다.
4. 정렬 기준은 `crawled_at DESC` — 최신 기사가 먼저 표시됩니다.

---

### CORS 설정

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
```

프론트엔드(Vite 개발 서버, 기본 포트 5173)에서만 요청을 허용합니다.  
읽기 전용 API이므로 `GET` 메서드만 허용합니다.

---

## 개발 참고사항

- DB 경로는 `main.py` 상단의 `DB_PATH` 변수로 관리됩니다.
- 프로덕션 배포 시 `allow_origins`를 실제 도메인으로 변경하세요.
- `uvicorn main:app --reload` 의 `--reload` 옵션은 개발 전용입니다. 운영 환경에서는 제거하세요.
