from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.auth_service import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
)
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/register")
def register(
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(None),
    db: Session = Depends(get_db),
):
    user = register_user(db, email, password, name)
    return {"message": "회원가입이 완료되었습니다.", "user_id": user.id}


@router.post("/login")
def login(
    email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)
):
    user = authenticate_user(db, email, password)
    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
