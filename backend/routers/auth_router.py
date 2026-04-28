import os
from datetime import datetime, timedelta
from typing import Optional

import jwt  # PyJWT 라이브러리 설치 필요: pip install pyjwt
from fastapi import APIRouter, Depends, HTTPException, Response, Body
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.auth_service import AuthService
from models.user import User

# --- 설정 (실제 운영 시에는 .env 환경변수로 관리하세요) ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24시간

# 카카오 설정
KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID", "여러분의_REST_API_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:3000/auth/kakao/callback")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
auth_service = AuthService(client_id=KAKAO_CLIENT_ID, redirect_uri=KAKAO_REDIRECT_URI)

# --- 유틸리티: JWT 토큰 생성 함수 ---
def create_service_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)

# --- 최종 라우터 엔드포인트 ---
@router.post("/kakao/login")
async def kakao_login(
    response: Response,
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db)
):
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="인가 코드가 없습니다.")
    
    try:
        kakao_access_token = await auth_service.get_kakao_access_token(code)
        