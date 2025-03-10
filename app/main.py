from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import npc_routes, auth_routes

app = FastAPI()

# 개발 환경에서는 모든 origin을 허용하고, 프로덕션에서는 특정 도메인만 허용
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # 개발 환경
    "https://yourdomain.com",  # 프로덕션 환경 (실제 도메인으로 변경 필요)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(npc_routes.router)
app.include_router(auth_routes.router)
