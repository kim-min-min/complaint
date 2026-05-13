import os
import asyncio
from pathlib import Path

import httpx
from dotenv import load_dotenv

from services.complaint_service import OPENAI_API_KEY, OPENAI_BASE_URL

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = 1536


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


async def create_embedding(text: str) -> list[float]:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise ValueError("임베딩할 텍스트가 비어 있습니다.")

    request_body = {
        "model": OPENAI_EMBEDDING_MODEL,
        "input": cleaned[:8000],
        "dimensions": EMBEDDING_DIMENSIONS,
    }
    url = f"{OPENAI_BASE_URL.rstrip('/')}/embeddings"
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=45) as client:
        for attempt in range(6):
            try:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    json=request_body,
                )
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code not in {429, 500, 502, 503, 504} or attempt == 5:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 5:
                    raise
                await asyncio.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError("OpenAI 임베딩 요청에 실패했습니다.") from last_error

    embeddings = data.get("data") or []
    if not embeddings:
        raise RuntimeError("OpenAI 임베딩 응답이 비어 있습니다.")
    return embeddings[0]["embedding"]
