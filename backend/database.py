import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://complaint:complaint@127.0.0.1:5432/complaint",
)
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"

engine = create_async_engine(
    DATABASE_URL,
    echo=DATABASE_ECHO,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db


async def check_database_connection() -> bool:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
