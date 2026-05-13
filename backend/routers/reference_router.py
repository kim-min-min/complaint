from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.ai_usage_log import AiUsageLog
from schemas.complaint import ReferenceSearchRequest, ReferenceSearchResponse
from services.auth_service import get_current_user
from services.reference_service import infer_charge_candidates, search_references
from services.usage_service import DailyUsageLimitExceeded, ensure_daily_usage_available, get_today_usage_summary, new_usage_log

router = APIRouter(prefix="/api/references", tags=["References"])


@router.post("/search", response_model=ReferenceSearchResponse)
async def search_reference_candidates(payload: ReferenceSearchRequest, request: Request, db: AsyncSession = Depends(get_db)):
    current_user = await get_current_user(request, db)
    try:
        await ensure_daily_usage_available(db, current_user.id)
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

    usage_log: AiUsageLog | None = None
    try:
        analysis = await infer_charge_candidates(payload)
        usage_log = new_usage_log(
            user_id=current_user.id,
            complaint_id=None,
            ai_job_id=None,
            request_type="reference",
            status="completed",
        )
        db.add(usage_log)
        await db.commit()
    except Exception as exc:
        if usage_log:
            usage_log.status = "failed"
            await db.commit()
        raise HTTPException(status_code=502, detail=f"죄명 후보 생성 중 오류가 발생했습니다: {exc}") from exc

    charge_items = await search_references(
        db,
        payload,
        [item["label"] for item in analysis.candidates],
        analysis.search_keywords,
        analysis.search_query,
    )
    reason_by_label = {item["label"]: item.get("reason", "") for item in analysis.candidates}
    for item in charge_items:
        item.reason = reason_by_label.get(item.label, "")

    usage = await get_today_usage_summary(db, current_user.id)
    return ReferenceSearchResponse(
        is_meaningful_case=analysis.is_meaningful_case,
        invalid_reason=analysis.invalid_reason,
        candidates=charge_items,
        search_keywords=analysis.search_keywords,
        search_query=analysis.search_query,
        fact_improvement_items=analysis.fact_improvement_items,
        reason_improvement_items=analysis.reason_improvement_items,
        usage_limit=usage.limit,
        usage_used=usage.used,
        usage_remaining=usage.remaining,
    )
