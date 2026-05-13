from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from services.auth_service import (
    clear_auth_cookie,
    create_access_token,
    exchange_kakao_code,
    get_current_user,
    kakao_login_url,
    set_auth_cookie,
    upsert_kakao_user,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class KakaoLoginRequest(BaseModel):
    code: str


@router.get("/kakao/login-url")
async def get_kakao_login_url():
    return {"login_url": kakao_login_url()}


@router.post("/kakao/login")
async def kakao_login(request: KakaoLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    kakao_profile = await exchange_kakao_code(request.code)
    user = await upsert_kakao_user(db, kakao_profile)
    access_token = create_access_token(user)
    set_auth_cookie(response, access_token)
    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": user.email,
    }


@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_current_user(request, db)
    return {
        "id": user.id,
        "nickname": user.nickname,
        "email": user.email,
    }


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}
