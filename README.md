# Alive-V 프로젝트

## 실행 방법

### 1. 로컬 개발환경 실행

1. `.env.dev` 파일을 설정합니다.
2. 아래 명령어를 실행합니다:
   ```bash
   docker-compose -f docker-compose.dev.yml up
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

---

## 주요 포트

- **API 서버**: `8000`
- **PostgreSQL 데이터베이스**: `5432`
