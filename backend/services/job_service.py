import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_job import AiJob
from models.complaint import Complaint
from schemas.complaint import ComplaintGenerateRequest
from services.cleanup_service import cleanup_expired_records
from services.complaint_service import OPENAI_MODEL
from services.crypto_service import decrypt_text, encrypt_text
from services.usage_service import ensure_daily_usage_available, new_usage_log

DEFAULT_USER_ID = 1
JOB_TTL_HOURS = 24


def _expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=JOB_TTL_HOURS)


async def ensure_dev_user(db: AsyncSession) -> int:
    from models.user import User

    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()
    if user:
        return user.id

    user = User(id=DEFAULT_USER_ID, kakao_id=0, nickname="dev-user", email=None)
    db.add(user)
    await db.flush()
    return user.id


async def create_generation_job(
    db: AsyncSession,
    payload: ComplaintGenerateRequest,
    user_id: int,
    request_type: str = "initial",
) -> AiJob:
    await cleanup_expired_records(db)
    await ensure_daily_usage_available(db, user_id)
    expires_at = _expires_at()
    complaint = Complaint(
        user_id=user_id,
        status="queued",
        expires_at=expires_at,
    )
    db.add(complaint)
    await db.flush()

    encrypted_payload = encrypt_text(payload.model_dump_json())
    job = AiJob(
        complaint_id=complaint.id,
        user_id=user_id,
        request_type=request_type,
        status="queued",
        attempts=0,
        encrypted_payload=encrypted_payload,
        expires_at=expires_at,
    )
    db.add(job)
    await db.flush()

    db.add(
        new_usage_log(
            user_id=user_id,
            complaint_id=complaint.id,
            ai_job_id=job.id,
            request_type=request_type,
        )
    )
    await db.commit()
    await db.refresh(job)
    return job


async def get_job(db: AsyncSession, job_id: int) -> AiJob | None:
    result = await db.execute(select(AiJob).where(AiJob.id == job_id))
    return result.scalar_one_or_none()


def payload_from_job(job: AiJob) -> ComplaintGenerateRequest:
    if not job.encrypted_payload:
        raise ValueError("작업 payload가 없습니다.")
    data = json.loads(decrypt_text(job.encrypted_payload))
    return ComplaintGenerateRequest(**data)


def result_from_job(job: AiJob) -> str | None:
    if not job.encrypted_result:
        return None
    return decrypt_text(job.encrypted_result)


def current_model_name() -> str:
    return OPENAI_MODEL
