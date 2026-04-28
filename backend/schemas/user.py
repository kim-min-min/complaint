from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

# 1. 프론트엔드에서 백엔드로 '인가 코드'를 보낼 때 사용
class KakaoLoginRequest(BaseModel):
    code: str

# 2. 로그인 성공 후 프론트엔드로 사용자 정보를 응답할 때 사용
class UserResponse(BaseModel):
    id: int
    nickname: str
    email: Optional[str] = None
    created_at: datetime

    # SQLAlchemy 모델 객체를 Pydantic에서 읽을 수 있게 설정 (2.0 버전 방식)
    model_config = ConfigDict(from_attributes=True)

# 3. 토큰 정보와 사용자 정보를 한꺼번에 보낼 때
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse