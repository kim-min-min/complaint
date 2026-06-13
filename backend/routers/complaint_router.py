from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from schemas.complaint import (
    ComplaintGenerateRequest,
    ComplaintJobCreateResponse,
    ComplaintJobStatusResponse,
    ComplaintPdfRequest,
)
from services.auth_service import get_current_user
from services.job_service import create_generation_job, get_job, result_from_job
from services.pdf_service import build_complaint_pdf
from services.usage_service import DailyUsageLimitExceeded, get_today_usage_summary
from tasks.complaint_tasks import generate_complaint_task

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])


@router.post("/generate-async", response_model=ComplaintJobCreateResponse)
async def generate_async(
    payload: ComplaintGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    current_user: User = await get_current_user(request, db)
    try:
        job = await create_generation_job(db, payload, user_id=current_user.id, request_type="complaint_generation")
    except DailyUsageLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "limit": exc.limit,
                "used": exc.used,
                "remaining": exc.remaining,
            },
        ) from exc

    generate_complaint_task.delay(job.id)
    usage = await get_today_usage_summary(db, job.user_id)
    return ComplaintJobCreateResponse(
        complaint_id=job.complaint_id,
        job_id=job.id,
        status=job.status,
        request_type=job.request_type,
        usage_limit=usage.limit,
        usage_used=usage.used,
        usage_remaining=usage.remaining,
    )


@router.get("/jobs/{job_id}", response_model=ComplaintJobStatusResponse)
async def job_status(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    return ComplaintJobStatusResponse(
        complaint_id=job.complaint_id,
        job_id=job.id,
        status=job.status,
        complaint_text=result_from_job(job) if job.status == "completed" else None,
        error_message=job.error_message,
    )


@router.post("/pdf")
async def build_pdf_from_current_document(pdf_request: ComplaintPdfRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    pdf_bytes = build_complaint_pdf(pdf_request.payload, pdf_request.complaint_text)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="complaint-draft.pdf"'},
    )
