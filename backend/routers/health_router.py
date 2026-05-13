from fastapi import APIRouter, HTTPException

from database import check_database_connection

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/db")
async def database_health():
    try:
        await check_database_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DB 연결 실패: {exc}") from exc
    return {"status": "ok"}
