import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User

load_dotenv()

KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USERINFO_URL = "https://kapi.kakao.com/v2/user/me"

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI", "http://localhost:5173/auth/kakao/callback")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-secret-before-production")
JWT_EXPIRES_SECONDS = int(os.getenv("JWT_EXPIRES_SECONDS", "86400"))
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "access_token")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


def kakao_login_url() -> str:
    if not KAKAO_REST_API_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_REST_API_KEY가 설정되지 않았습니다.")

    query = urlencode(
        {
            "client_id": KAKAO_REST_API_KEY,
            "redirect_uri": KAKAO_REDIRECT_URI,
            "response_type": "code",
        }
    )
    return f"{KAKAO_AUTH_URL}?{query}"


async def exchange_kakao_code(code: str) -> dict:
    token_payload = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    if KAKAO_CLIENT_SECRET:
        token_payload["client_secret"] = KAKAO_CLIENT_SECRET

    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post(
            KAKAO_TOKEN_URL,
            data=token_payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        )
        try:
            token_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=_kakao_error_message("카카오 토큰 발급", exc.response),
            ) from exc
        token_data = token_response.json()

        user_response = await client.get(
            KAKAO_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        try:
            user_response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=_kakao_error_message("카카오 사용자 정보 조회", exc.response),
            ) from exc
        return user_response.json()


async def upsert_kakao_user(db: AsyncSession, kakao_profile: dict) -> User:
    kakao_id = int(kakao_profile["id"])
    account = kakao_profile.get("kakao_account") or {}
    profile = account.get("profile") or {}
    nickname = profile.get("nickname") or f"kakao-{kakao_id}"
    email = account.get("email")

    result = await db.execute(select(User).where(User.kakao_id == kakao_id))
    user = result.scalar_one_or_none()
    if user:
        user.nickname = nickname
        user.email = email
        user.updated_at = datetime.now(timezone.utc)
    else:
        user = User(kakao_id=kakao_id, nickname=nickname, email=email)
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


def create_access_token(user: User) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "kakao_id": user.kakao_id,
        "iat": now,
        "exp": now + JWT_EXPIRES_SECONDS,
    }
    return _encode_jwt(payload)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRES_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


async def get_current_user(request: Request, db: AsyncSession) -> User:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    try:
        payload = _decode_jwt(token)
        user_id = int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="로그인이 만료되었거나 유효하지 않습니다.") from exc

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _encode_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_part = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_b64url_encode(signature)}"


def _decode_jwt(token: str) -> dict:
    header_part, payload_part, signature_part = token.split(".")
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual = _b64url_decode(signature_part)
    if not hmac.compare_digest(expected, actual):
        raise ValueError("invalid signature")

    payload = json.loads(_b64url_decode(payload_part))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("expired token")
    return payload


def _kakao_error_message(step: str, response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"{step}에 실패했습니다. 상태 코드: {response.status_code}"

    error = data.get("error") or data.get("code") or response.status_code
    description = data.get("error_description") or data.get("msg") or data.get("message") or data
    return f"{step}에 실패했습니다: {error} - {description}"
