from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# 1. URL에 '+asyncpg'를 붙여 비동기 드라이버를 사용한다고 명시합니다.
SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/complaint_db"

# 2. create_engine 대신 create_async_engine을 사용합니다.
engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True) # echo=True를 주면 쿼리 로그가 찍힙니다.

# 3. 비동기 세션을 생성하는 팩토리를 만듭니다.
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    autocommit=False, 
    autoflush=False
)

Base = declarative_base()

# 4. 의존성 주입 함수도 비동기(async def)로 변경합니다.
async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
        # async with 블록을 벗어나면 자동으로 세션이 안전하게 종료(close)됩니다.