import uuid
import os
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_connection, release_connection
from app.utils.password import hash_password, verify_password

# 환경 변수 및 상수
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# JWT 인증 스키마
oauth2_scheme = HTTPBearer()


def create_token(data: dict, expires_delta: timedelta) -> str:
    """JWT 토큰을 생성합니다."""
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + expires_delta})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(data: dict) -> str:
    """액세스 토큰을 생성합니다."""
    return create_token(data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: dict) -> str:
    """리프레시 토큰을 생성합니다."""
    return create_token(data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
):
    """현재 인증된 사용자의 정보를 반환합니다."""
    try:
        # 토큰 검증
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )

        # 사용자 정보 조회
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id, email, name FROM "User" WHERE id = %s', (user_id,)
                )
                user = cursor.fetchone()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found",
                    )
                return {"id": user[0], "email": user[1], "name": user[2]}
        finally:
            release_connection(conn)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def register_user(email: str, password: str, name: str = None):
    """새로운 사용자를 등록합니다."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 이메일 중복 확인
            cursor.execute('SELECT id FROM "User" WHERE email = %s', (email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 가입된 이메일입니다.",
                )

            # 사용자 생성
            user_id = str(uuid.uuid4())
            hashed_password = hash_password(password)
            cursor.execute(
                'INSERT INTO "User" (id, email, password, name, "createdAt") VALUES (%s, %s, %s, %s, %s)',
                (user_id, email, hashed_password, name, datetime.utcnow()),
            )
            conn.commit()
            return {"user_id": user_id}

    except Exception as e:
        conn.rollback()
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"회원가입 실패: {str(e)}",
            )
        raise
    finally:
        release_connection(conn)


def authenticate_user(email: str, password: str):
    """사용자 인증을 수행합니다."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, password FROM "User" WHERE email = %s', (email,))
            user = cursor.fetchone()
            if not user or not verify_password(password, user[1]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="이메일 또는 비밀번호가 일치하지 않습니다.",
                )
            return {"user_id": user[0]}
    finally:
        release_connection(conn)
