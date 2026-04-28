import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.user import User
from schemas.user import UserCreate  # 유저 생성을 위한 스키마가 있다고 가정

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"

class AuthService:
    def __init__(self, client_id: str, redirect_uri: str):
        self.client_id = client_id
        self.redirect_uri = redirect_uri

    async def get_kakao_access_token(self, code: str) -> str:
        """인가 코드로 엑세스 토큰 발급"""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(KAKAO_TOKEN_URL, data=data)
            response.raise_for_status()
            return response.json().get("access_token")

    async def get_kakao_user_info(self, access_token: str) -> dict:
        """엑세스 토큰으로 사용자 정보 가져오기"""
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(KAKAO_USER_INFO_URL, headers=headers)
            response.raise_for_status()
            return response.json()

    async def authenticate_user(self, db: AsyncSession, kakao_info: dict) -> User:
        """DB에서 유저 확인 후 없으면 생성 (Upsert 로직)"""
        kakao_id = str(kakao_info.get("id"))
        properties = kakao_info.get("properties", {})
        nickname = properties.get("nickname")

        # 1. 기존 유저 존재 확인
        result = await db.execute(select(User).where(User.kakao_id == kakao_id))
        user = result.scalars().first()

        # 2. 유저가 없으면 신규 생성
        if not user:
            user = User(
                kakao_id=kakao_id,
                nickname=nickname,
                # 필요한 필드 추가 (예: profile_image)
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        
        return user