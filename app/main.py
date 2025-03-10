from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import npc_routes, auth_routes

app = FastAPI()

# 개발 환경에서는 모든 origin을 허용하고, 프로덕션에서는 특정 도메인만 허용
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # 개발 환경
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite 개발 서버
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(npc_routes.router)
app.include_router(auth_routes.router)
