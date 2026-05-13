from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from schemas.complaint import (
    ComplaintGenerateRequest,
    ComplaintGenerateResponse,
    ComplaintJobCreateResponse,
    ComplaintJobStatusResponse,
    ComplaintPdfRequest,
)
from services.complaint_service import generate_complaint, get_complaint, get_missing_fields, save_complaint
from services.auth_service import get_current_user
from services.job_service import create_generation_job, get_job, result_from_job
from services.pdf_service import build_complaint_pdf
from services.usage_service import DailyUsageLimitExceeded, get_today_usage_summary
from tasks.complaint_tasks import generate_complaint_task

router = APIRouter(prefix="/api/complaints", tags=["Complaints"])


@router.post("/generate", response_model=ComplaintGenerateResponse)
async def generate(payload: ComplaintGenerateRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    try:
        complaint_text, used_fallback = await generate_complaint(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM 호출 중 오류가 발생했습니다: {exc}") from exc

    complaint_id = save_complaint(payload, complaint_text)
    return ComplaintGenerateResponse(
        complaint_id=complaint_id,
        complaint_text=complaint_text,
        missing_fields=get_missing_fields(payload),
        used_fallback=used_fallback,
    )


@router.post("/generate-async", response_model=ComplaintJobCreateResponse)
async def generate_async(
    payload: ComplaintGenerateRequest,
    request: Request,
    request_type: Literal["initial", "final"] = Query("initial"),
    db: AsyncSession = Depends(get_db),
):
    current_user: User = await get_current_user(request, db)
    try:
        job = await create_generation_job(db, payload, user_id=current_user.id, request_type=request_type)
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


@router.get("/{complaint_id}/pdf")
async def download_pdf(complaint_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    item = get_complaint(complaint_id)
    if not item:
        raise HTTPException(status_code=404, detail="고소장 초안을 찾을 수 없습니다. 다시 생성해 주세요.")

    payload, complaint_text = item
    pdf_bytes = build_complaint_pdf(payload, complaint_text)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="complaint-draft.pdf"'},
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
