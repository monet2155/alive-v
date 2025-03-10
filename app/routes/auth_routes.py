from fastapi import APIRouter, status, Form, Depends
from fastapi.responses import RedirectResponse
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
)
import os
import httpx
import uuid
from datetime import datetime
from urllib.parse import urlencode

router = APIRouter()

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.post("/register")
def register(email: str = Form(...), password: str = Form(...), name: str = Form(None)):
    result = register_user(email, password, name)
    return {"message": "회원가입이 완료되었습니다.", "user_id": result["user_id"]}


@router.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email, password)
    access_token = create_access_token({"sub": user["user_id"]})
    refresh_token = create_refresh_token({"sub": user["user_id"]})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.get("/google/callback")
async def google_callback(code: str):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    try:
        # 구글 토큰 획득
        async with httpx.AsyncClient() as client:
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": google_client_id,
                    "client_secret": google_client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_res.raise_for_status()
            tokens = token_res.json()

            # 사용자 정보 획득
            userinfo_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
            )
            userinfo_res.raise_for_status()
            userinfo = userinfo_res.json()

        # 사용자 생성 또는 조회
        from app.database import get_connection, release_connection

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id FROM "User" WHERE email = %s', (userinfo["email"],)
                )
                user = cursor.fetchone()

                if not user:
                    user_id = str(uuid.uuid4())
                    cursor.execute(
                        'INSERT INTO "User" (id, email, provider, "providerId", name, "createdAt") VALUES (%s, %s, %s, %s, %s, %s)',
                        (
                            user_id,
                            userinfo["email"],
                            "GOOGLE",
                            userinfo["id"],
                            userinfo.get("name"),
                            datetime.utcnow(),
                        ),
                    )
                    conn.commit()
                else:
                    user_id = user[0]

            # JWT 토큰 생성 및 리다이렉트
            access_token = create_access_token({"sub": user_id})
            refresh_token = create_refresh_token({"sub": user_id})
            params = urlencode(
                {"access_token": access_token, "refresh_token": refresh_token}
            )

            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/callback/success?{params}",
                status_code=status.HTTP_302_FOUND,
            )

        except Exception:
            conn.rollback()
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/callback/error",
                status_code=status.HTTP_302_FOUND,
            )
        finally:
            release_connection(conn)

    except Exception:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/auth/callback/error",
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/auth/me")
async def get_me(user=Depends(get_current_user)):
    return user
