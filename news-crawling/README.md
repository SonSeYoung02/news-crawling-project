# 뉴스 원문 수집 파이프라인

네이버뉴스, Google News, GeekNews, Reddit AI, GitHub Trending, Hugging Face, arXiv, dev.to의 기사와 피드 내용을 수집해 SQLite에 저장합니다. Gemini 등 LLM은 사용하지 않으며 번역·요약·AI 분류를 수행하지 않습니다. API 키가 필요하지 않습니다.

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --run
```

`python main.py --schedule`은 매일 한국 시간 08:00에 1회 수집합니다. 상시 반복 수집을 시작하려는 경우에만 사용합니다.

## 수집 및 저장 방식

- 수집한 제목·본문은 원문 언어로 저장하고 카테고리·태그는 각 수집기 값을 사용합니다.
- URL로 중복을 확인하며 기존 URL도 재수집한 원문과 메타데이터로 갱신합니다. 빈 본문으로 기존 본문을 덮어쓰지 않습니다.
- 수집기에서 제공하는 내용은 전체 기사, 피드 본문, 초록 또는 소개문일 수 있습니다. 원문 링크로 출처 내용을 확인할 수 있습니다.
- 소스별 요청 오류는 로그에 기록하며 다른 소스 수집은 계속합니다.
- `news.db`와 `pipeline.log`는 로컬 실행 데이터이며 Git에 커밋하지 않습니다.
- 기존 `article_analysis` 테이블은 이전 데이터 호환성을 위해 보존하지만 새 수집에서는 사용하지 않습니다.

## 구성

- `main.py`: 1회 수집 및 예약 실행
- `crawlers/`: 소스별 수집기
- `db.py`: 원문 저장·갱신 및 SQLite 스키마
- `config.py`: DB 경로, 요청 헤더·시간 제한, 예약 시각
- `requirements.txt`: 수집용 의존성 (`google-genai` 제거)

## 검증

```powershell
python -m unittest test_direct_content -v
```

테스트는 외부 수집을 모킹하며 AI 없이 원문 보존, 여러 소스 저장, 중복 기사 갱신을 확인합니다.
