from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth_router import router as auth_router
from routers.complaint_router import router as complaint_router
from routers.health_router import router as health_router
from routers.reference_router import router as reference_router
from routers.usage_router import router as usage_router

app = FastAPI(title="나홀로 소송 AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(complaint_router)
app.include_router(health_router)
app.include_router(reference_router)
app.include_router(usage_router)


@app.get("/")
def read_root():
    return {"message": "나홀로 소송 AI 백엔드 실행 중"}
