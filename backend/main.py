from contextlib import asynccontextmanager
from fastapi import FastAPI

# database.py에서 설정한 engine과 Base를 가져옵니다.
from database import engine, Base

# 🔥 [매우 중요] 테이블을 생성하려면 모델 파일이 반드시 여기에 import 되어 있어야 합니다!
# from models.user import User  # 나중에 user.py를 만들면 주석을 해제하세요.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # [1] 서버가 켜질 때 실행되는 구간 (여기에 테이블 생성 코드 작성)
    print("🚀 서버 시작: DB 테이블 생성을 시도합니다...")
    
    # 비동기 엔진에서는 run_sync를 사용해 동기 함수인 create_all을 실행합니다.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    print("✅ DB 테이블 생성 완료!")
    
    yield # 이 시점부터 FastAPI가 API 요청을 받기 시작합니다.
    
    # [2] 서버가 꺼질 때 실행되는 구간 (필요시 자원 정리 코드 작성)
    print("🛑 서버 종료")


# 앱 생성 시 lifespan을 연결해 줍니다.
app = FastAPI(title="나홀로 소송 AI API", lifespan=lifespan)


@app.get("/")
def read_root():
    return {"message": "나홀로 소송 AI 백엔드 실행 중"}