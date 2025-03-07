from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import npc_routes, auth_routes

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["https://yourdomain.com"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST"],
#     allow_headers=["Authorization", "Content-Type"],
# )

app.include_router(npc_routes.router)
app.include_router(auth_routes.router)
