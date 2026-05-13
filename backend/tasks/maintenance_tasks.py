import asyncio

from celery_app import celery_app
from database import AsyncSessionLocal, engine
from services.cleanup_service import cleanup_expired_records


@celery_app.task(name="maintenance.cleanup_expired")
def cleanup_expired_task() -> int:
    return asyncio.run(_cleanup_expired())


async def _cleanup_expired() -> int:
    await engine.dispose()
    try:
        async with AsyncSessionLocal() as db:
            return await cleanup_expired_records(db)
    finally:
        await engine.dispose()
