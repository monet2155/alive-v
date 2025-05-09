# Alive-V 프로젝트

AI 기반 대화형 캐릭터 시스템을 구현한 프로젝트입니다. NPC와의 자연스러운 대화와 이벤트 기반 상호작용을 지원합니다.

## 기술 스택

- **백엔드**: FastAPI (Python 3.11+)
- **데이터베이스**: PostgreSQL
- **AI 모델**: OpenAI GPT, Anthropic Claude
- **의존성 관리**: Poetry
- **API 서버**: Uvicorn

## 프로젝트 구조

```
alive-v/
├── app/
│   ├── routes/              # API 엔드포인트
│   │   ├── npc_routes.py    # NPC 관련 API
│   │   ├── event_routes.py  # 이벤트 관련 API
│   │   └── universe_routes.py # 유니버스 관련 API
│   │
│   ├── services/           # 비즈니스 로직
│   │   ├── npc_service.py     # NPC 관리 서비스
│   │   ├── session_service.py # 대화 세션 관리
│   │   ├── memory_service.py  # NPC 메모리 관리
│   │   ├── event_service.py   # 이벤트 처리
│   │   └── universe_service.py # 유니버스 관리
│   │
│   ├── config.py           # 환경 설정
│   ├── database.py         # 데이터베이스 연결
│   ├── main.py            # FastAPI 애플리케이션 진입점
│   ├── models.py          # Pydantic 데이터 모델
│   └── prompts.py         # AI 프롬프트 템플릿
│
├── prompt_*.txt           # AI 프롬프트 템플릿 파일들
├── pyproject.toml        # 프로젝트 의존성
└── poetry.lock          # 의존성 잠금 파일
```

## 주요 기능

- **NPC 관리**: AI 기반 NPC 생성 및 관리
- **대화 시스템**: 자연스러운 대화 세션 관리
- **이벤트 시스템**: 상황별 이벤트 처리
- **메모리 시스템**: NPC의 대화 및 상호작용 기억
- **유니버스 관리**: 게임 세계 설정 관리

## 실행 방법

### 1. 로컬 개발환경 실행

1. `.env` 파일을 설정합니다.

2. 아래 명령어를 실행합니다:
   ```bash
   poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### 2. 개발 서버 실행

1. `.env.staging` 파일을 설정합니다.
2. 아래 명령어를 실행합니다:
   ```bash
   docker-compose -f docker-compose.staging.yml up
   ```

### 3. 운영 서버 실행

1. `.env.prod` 파일을 설정합니다.
2. 아래 명령어를 실행합니다:
   ```bash
   docker-compose -f docker-compose.prod.yml up
   ```

---

## 의존성 설치

프로젝트 의존성은 `poetry`를 사용하여 관리됩니다. 아래 명령어로 의존성을 설치할 수 있습니다:

```bash
poetry install
```

## 주요 포트

- **API 서버**: `8000`
- **PostgreSQL 데이터베이스**: `5432`

## API 문서

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 주요 API 엔드포인트

- **NPC 관련**: `/api/npc/*`
- **이벤트 관련**: `/api/event/*`
- **유니버스 관련**: `/api/universe/*`

## 환경 변수

프로젝트는 다음 환경 변수들을 사용합니다:

- `DATABASE_URL`: PostgreSQL 데이터베이스 연결 문자열
- `OPENAI_API_KEY`: OpenAI API 키
- `ANTHROPIC_API_KEY`: Anthropic API 키

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
