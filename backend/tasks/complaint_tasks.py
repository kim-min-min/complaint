import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from database import AsyncSessionLocal, engine
from models.ai_job import AiJob
from models.ai_usage_log import AiUsageLog
from models.complaint import Complaint
from services.complaint_service import generate_complaint
from services.crypto_service import encrypt_text
from services.job_service import payload_from_job


@celery_app.task(name="complaints.generate")
def generate_complaint_task(job_id: int) -> None:
    asyncio.run(_run_generate_complaint(job_id))


async def _run_generate_complaint(job_id: int) -> None:
    await engine.dispose()
    try:
        await _generate_complaint(job_id)
    finally:
        await engine.dispose()


async def _generate_complaint(job_id: int) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AiJob).where(AiJob.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return

        complaint = await db.get(Complaint, job.complaint_id)
        usage_log = await _get_usage_log(db, job.id)
        now = datetime.now(timezone.utc)
        job.status = "running"
        job.started_at = now
        job.attempts = (job.attempts or 0) + 1
        if usage_log:
            usage_log.status = "running"
        if complaint:
            complaint.status = "generating"
        await db.commit()

        try:
            payload = payload_from_job(job)
            complaint_text, _used_fallback = await generate_complaint(payload)

            job.encrypted_result = encrypt_text(complaint_text)
            job.encrypted_payload = None
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            if usage_log:
                usage_log.status = "completed"
            if complaint:
                complaint.status = "completed"
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            if usage_log:
                usage_log.status = "failed"
            if complaint:
                complaint.status = "failed"
                complaint.error_message = str(exc)
        finally:
            await db.commit()


async def _get_usage_log(db, job_id: int) -> AiUsageLog | None:
    result = await db.execute(select(AiUsageLog).where(AiUsageLog.ai_job_id == job_id))
    return result.scalar_one_or_none()
