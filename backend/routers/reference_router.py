from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.complaint import ReferenceGuidanceRequest, ReferenceJobCreateResponse, ReferenceJobStatusResponse, ReferenceSearchRequest, SimilarPrecedentItem
from services.auth_service import get_current_user
from services.job_service import create_reference_job, get_job, json_result_from_job
from services.reference_service import build_precedent_guidance
from services.usage_service import DailyUsageLimitExceeded, get_today_usage_summary
from tasks.reference_tasks import process_reference_task

router = APIRouter(prefix="/api/references", tags=["References"])


async def _create_reference_job_response(
    *,
    payload: ReferenceSearchRequest,
    request: Request,
    db: AsyncSession,
    request_type: str,
) -> ReferenceJobCreateResponse:
    current_user = await get_current_user(request, db)
    try:
        job = await create_reference_job(db, payload, user_id=current_user.id, request_type=request_type)
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

    process_reference_task.delay(job.id)
    usage = await get_today_usage_summary(db, job.user_id)
    return ReferenceJobCreateResponse(
        complaint_id=job.complaint_id,
        job_id=job.id,
        status=job.status,
        request_type=job.request_type,
        usage_limit=usage.limit,
        usage_used=usage.used,
        usage_remaining=usage.remaining,
    )


@router.post("/analyze", response_model=ReferenceJobCreateResponse)
async def analyze_reference_candidates(payload: ReferenceSearchRequest, request: Request, db: AsyncSession = Depends(get_db)):
    return await _create_reference_job_response(
        payload=payload,
        request=request,
        db=db,
        request_type="reference_analysis",
    )


@router.post("/guidance", response_model=SimilarPrecedentItem)
async def build_reference_guidance(payload: ReferenceGuidanceRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await get_current_user(request, db)
    return await build_precedent_guidance(payload)


@router.get("/jobs/{job_id}", response_model=ReferenceJobStatusResponse)
async def reference_job_status(job_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    if job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")

    return ReferenceJobStatusResponse(
        complaint_id=job.complaint_id,
        job_id=job.id,
        status=job.status,
        result=json_result_from_job(job) if job.status == "completed" else None,
        error_message=job.error_message,
    )
