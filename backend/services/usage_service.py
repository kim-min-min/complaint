from dataclasses import dataclass
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_usage_log import AiUsageLog
from models.user import User
from services.complaint_service import OPENAI_MODEL

DAILY_AI_REQUEST_LIMIT = 10
UNLIMITED_AI_REQUEST_LIMIT = 999999
KST = ZoneInfo("Asia/Seoul")


class DailyUsageLimitExceeded(Exception):
    def __init__(self, limit: int, used: int) -> None:
        self.limit = limit
        self.used = used
        self.remaining = max(limit - used, 0)
        super().__init__("오늘 사용 가능한 AI 요청 횟수를 모두 사용했습니다.")


@dataclass(frozen=True)
class UsageSummary:
    limit: int
    used: int

    @property
    def remaining(self) -> int:
        return max(self.limit - self.used, 0)


def today_kst():
    return datetime.now(KST).date()


def _env_set(name: str) -> set[str]:
    return {item.strip() for item in os.getenv(name, "").split(",") if item.strip()}


async def is_unlimited_ai_user(db: AsyncSession, user_id: int) -> bool:
    unlimited_ids = _env_set("UNLIMITED_AI_USER_IDS")
    if str(user_id) in unlimited_ids:
        return True

    unlimited_emails = {email.lower() for email in _env_set("UNLIMITED_AI_USER_EMAILS")}
    if not unlimited_emails:
        return False

    user = await db.get(User, user_id)
    return bool(user and user.email and user.email.lower() in unlimited_emails)


async def get_today_usage_summary(db: AsyncSession, user_id: int) -> UsageSummary:
    if await is_unlimited_ai_user(db, user_id):
        return UsageSummary(limit=UNLIMITED_AI_REQUEST_LIMIT, used=0)

    usage_date = today_kst()
    result = await db.execute(
        select(func.count(AiUsageLog.id)).where(
            AiUsageLog.user_id == user_id,
            AiUsageLog.usage_date == usage_date,
        )
    )
    used = int(result.scalar_one() or 0)
    return UsageSummary(limit=DAILY_AI_REQUEST_LIMIT, used=used)


async def ensure_daily_usage_available(db: AsyncSession, user_id: int) -> UsageSummary:
    summary = await get_today_usage_summary(db, user_id)
    if summary.remaining <= 0:
        raise DailyUsageLimitExceeded(limit=summary.limit, used=summary.used)
    return summary


def new_usage_log(
    *,
    user_id: int,
    complaint_id: int | None,
    ai_job_id: int | None,
    request_type: str,
    status: str = "queued",
) -> AiUsageLog:
    return AiUsageLog(
        user_id=user_id,
        complaint_id=complaint_id,
        ai_job_id=ai_job_id,
        usage_date=today_kst(),
        request_type=request_type,
        model=OPENAI_MODEL,
        status=status,
    )
