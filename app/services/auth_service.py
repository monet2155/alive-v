import uuid
import os
from datetime import datetime, timedelta
from jose import jwt
from fastapi import HTTPException, status
from app.database import get_connection, release_connection
from app.utils.password import hash_password, verify_password

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def register_user(email: str, password: str, name: str = None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM "User" WHERE email = %s', (email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

            user_id = str(uuid.uuid4())
            hashed_password = hash_password(password)
            now = datetime.utcnow()

            cursor.execute(
                """
                INSERT INTO "User" (id, email, password, name, "createdAt")
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, email, hashed_password, name, now),
            )
            conn.commit()
            return {"user_id": user_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"회원가입 실패: {e}")
    finally:
        release_connection(conn)


def authenticate_user(email: str, password: str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id, password FROM "User" WHERE email = %s', (email,))
            user = cursor.fetchone()
            if not user or not verify_password(password, user[1]):
                raise HTTPException(
                    status_code=401, detail="이메일 또는 비밀번호가 일치하지 않습니다."
                )

            return {"user_id": user[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"로그인 실패: {e}")
    finally:
        release_connection(conn)
