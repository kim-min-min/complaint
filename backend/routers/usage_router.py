from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.complaint import UsageTodayResponse
from services.auth_service import get_current_user
from services.cleanup_service import cleanup_expired_records
from services.usage_service import get_today_usage_summary

router = APIRouter(prefix="/api/usage", tags=["Usage"])


@router.get("/today", response_model=UsageTodayResponse)
async def today_usage(request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    await cleanup_expired_records(db)
    usage = await get_today_usage_summary(db, current_user.id)
    return UsageTodayResponse(
        limit=usage.limit,
        used=usage.used,
        remaining=usage.remaining,
    )
