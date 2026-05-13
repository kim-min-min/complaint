from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_job import AiJob
from models.complaint import Complaint


async def cleanup_expired_records(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    cleaned_count = 0

    job_result = await db.execute(
        select(AiJob).where(
            AiJob.expires_at.is_not(None),
            AiJob.expires_at <= now,
            or_(
                AiJob.encrypted_payload.is_not(None),
                AiJob.encrypted_result.is_not(None),
                AiJob.status != "expired",
            ),
        )
    )
    jobs = job_result.scalars().all()
    for job in jobs:
        job.encrypted_payload = None
        job.encrypted_result = None
        if job.status not in {"failed", "expired"}:
            job.status = "expired"
        cleaned_count += 1

    complaint_result = await db.execute(
        select(Complaint).where(
            Complaint.expires_at.is_not(None),
            Complaint.expires_at <= now,
            Complaint.status != "expired",
        )
    )
    complaints = complaint_result.scalars().all()
    for complaint in complaints:
        if complaint.status != "failed":
            complaint.status = "expired"
        cleaned_count += 1

    if cleaned_count:
        await db.commit()

    return cleaned_count
