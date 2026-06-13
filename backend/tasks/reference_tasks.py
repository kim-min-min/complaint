import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from database import AsyncSessionLocal, engine
from models.ai_job import AiJob
from models.ai_usage_log import AiUsageLog
from models.complaint import Complaint
from services.crypto_service import encrypt_text
from services.job_service import reference_payload_from_job
from services.reference_service import analyze_reference_points, infer_reference_query
from services.usage_service import get_today_usage_summary


@celery_app.task(name="references.process")
def process_reference_task(job_id: int) -> None:
    asyncio.run(_run_process_reference(job_id))


async def _run_process_reference(job_id: int) -> None:
    await engine.dispose()
    try:
        await _process_reference(job_id)
    finally:
        await engine.dispose()


async def _process_reference(job_id: int) -> None:
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
            payload = reference_payload_from_job(job)
            if job.request_type == "reference_analysis":
                response_data = await _build_reference_response(db, job.user_id, payload)
            else:
                raise ValueError(f"지원하지 않는 reference 작업 유형입니다: {job.request_type}")

            job.encrypted_result = encrypt_text(json.dumps(response_data, ensure_ascii=False))
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


async def _build_reference_response(db, user_id: int, payload) -> dict:
    analysis = await infer_reference_query(payload)
    usage = await get_today_usage_summary(db, user_id)
    response = await analyze_reference_points(
        db,
        payload,
        analysis,
        usage.limit,
        usage.used,
        usage.remaining,
    )
    return response.model_dump()


async def _get_usage_log(db, job_id: int) -> AiUsageLog | None:
    result = await db.execute(select(AiUsageLog).where(AiUsageLog.ai_job_id == job_id))
    return result.scalar_one_or_none()
