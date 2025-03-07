from fastapi import APIRouter, HTTPException, status, Form
from fastapi.responses import JSONResponse
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
)
import os
import httpx
import uuid
from datetime import datetime, timedelta

router = APIRouter()


@router.post("/register")
def register(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(None),
):
    result = register_user(email, password, name)
    return {"message": "회원가입이 완료되었습니다.", "user_id": result["user_id"]}


@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
):
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

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": google_client_id,
        "client_secret": google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        token_res = await client.post(token_url, data=token_data)
        token_res.raise_for_status()
        tokens = token_res.json()

        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        userinfo_res = await client.get(userinfo_url, headers=headers)
        userinfo_res.raise_for_status()
        userinfo = userinfo_res.json()

    email = userinfo["email"]
    provider_id = userinfo["id"]
    name = userinfo.get("name")

    from app.database import get_connection, release_connection

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT id FROM "User" WHERE email = %s', (email,))
            user = cursor.fetchone()

            if not user:
                user_id = str(uuid.uuid4())
                now = datetime.utcnow()
                cursor.execute(
                    """
                    INSERT INTO "User" (id, email, provider, "providerId", name, "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, email, "google", provider_id, name, now, now),
                )
                conn.commit()
            else:
                user_id = user[0]

        access_token = create_access_token({"sub": user_id})
        refresh_token = create_refresh_token({"sub": user_id})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"구글 로그인 실패: {e}")
    finally:
        release_connection(conn)
