import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, text

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import AsyncSessionLocal  # noqa: E402
from models.precedent import Precedent, PrecedentChunk  # noqa: E402
from services.embedding_service import EMBEDDING_DIMENSIONS, create_embeddings, vector_literal  # noqa: E402


CHUNK_WEIGHTS = {
    "issue": 0.3,
    "fact": 0.6,
    "outcome": 0.1,
}
EMBEDDING_BATCH_SIZE = 96


def _clean(value: object, limit: int | None = None) -> str:
    text_value = " ".join(str(value or "").split())
    return text_value[:limit] if limit else text_value


def _as_list(value: object, limit: int = 80) -> list[str]:
    if isinstance(value, list):
        return [_clean(item, limit) for item in value if _clean(item, limit)]
    if isinstance(value, str) and value.strip():
        return [_clean(value, limit)]
    return []


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _primary_case_name(primary_charge: str, case_name: str) -> str:
    if primary_charge:
        return primary_charge.removesuffix("죄")[:200]
    cleaned = _clean(case_name, 500)
    return cleaned.split("·", 1)[0].strip().rstrip(",")[:200] if cleaned else "미분류"


def _court_weight_score(value: str) -> float:
    if value == "high":
        return 0.9
    if value == "medium":
        return 0.6
    if value == "low":
        return 0.3
    return 0.5


def _chunk_items(item: dict[str, Any]) -> list[tuple[str, str, float]]:
    embedding_texts = _as_dict(item.get("embedding_texts"))
    chunks: list[tuple[str, str, float]] = []
    for chunk_type in ("issue", "fact", "outcome"):
        chunk_text = _clean(embedding_texts.get(chunk_type), 2500)
        if chunk_text:
            chunks.append((chunk_type, chunk_text, CHUNK_WEIGHTS[chunk_type]))
    return chunks


async def _insert_chunk_batch(
    rows: list[tuple[int, str, str, float]],
    skip_embeddings: bool,
) -> int:
    if not rows:
        return 0
    if skip_embeddings:
        embeddings = [[0.0] * EMBEDDING_DIMENSIONS for _ in rows]
    else:
        embeddings = await create_embeddings([row[2] for row in rows])

    async with AsyncSessionLocal() as db:
        for (precedent_id, chunk_type, chunk_text, weight), embedding in zip(rows, embeddings, strict=True):
            await db.execute(
                text(
                    """
                    INSERT INTO precedent_chunks (precedent_id, chunk_type, text, embedding, weight)
                    VALUES (:precedent_id, :chunk_type, :chunk_text, CAST(:embedding AS vector), :weight)
                    """
                ),
                {
                    "precedent_id": precedent_id,
                    "chunk_type": chunk_type,
                    "chunk_text": chunk_text,
                    "embedding": vector_literal(embedding),
                    "weight": weight,
                },
            )
        await db.commit()
    return len(rows)


async def import_precedents(path: Path, reset: bool, limit: int | None, skip_embeddings: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("판례 JSON은 리스트 형식이어야 합니다.")
    if limit:
        data = data[:limit]

    async with AsyncSessionLocal() as db:
        if reset:
            await db.execute(delete(PrecedentChunk))
            await db.execute(delete(Precedent))
            await db.commit()

    imported = 0
    chunked = 0
    skipped = 0
    pending_chunks: list[tuple[int, str, str, float]] = []

    for item in data:
        source_id = _clean(item.get("source_id"), 80)
        if not source_id:
            skipped += 1
            continue

        chunks = _chunk_items(item)
        if not chunks:
            skipped += 1
            continue

        raw_sections = _as_dict(item.get("raw_sections"))
        quality = _as_dict(item.get("quality"))
        primary_charge = _clean(item.get("primary_charge"), 120)
        case_name = _clean(item.get("case_name"), 500) or _clean(item.get("case_number"), 120) or source_id

        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(Precedent).where(Precedent.source_id == source_id))
            precedent = existing.scalar_one_or_none()
            if not precedent:
                precedent = Precedent(source_id=source_id)
                db.add(precedent)

            precedent.source = _clean(item.get("source") or "law.go.kr", 60)
            precedent.source_url = _clean(item.get("source_url"), 500)
            precedent.category = _clean(primary_charge, 80) or "미분류"
            precedent.case_number = _clean(item.get("case_number"), 120) or source_id
            precedent.case_name = case_name
            precedent.primary_case_name = _primary_case_name(primary_charge, case_name)
            precedent.primary_charge = primary_charge
            precedent.court_name = _clean(item.get("court_name"), 160)
            precedent.court_level = _clean(item.get("court_level"), 40)
            precedent.verdict_date = _clean(item.get("verdict_date"), 40)
            precedent.verdict_type = _clean(item.get("verdict_type"), 120)
            precedent.case_type = _clean(item.get("case_type"), 80)
            precedent.charges = _as_list(item.get("case_charges"), 120)
            precedent.keywords = _as_list(item.get("search_tags"), 120)
            precedent.holding = _clean(raw_sections.get("holding"))
            precedent.summary = _clean(raw_sections.get("summary"))
            precedent.reasoning_excerpt = _clean(raw_sections.get("reasoning_excerpt"))
            precedent.fact_context = _clean(_as_dict(item.get("embedding_texts")).get("fact"))
            precedent.refs_articles = ""
            precedent.refs_cases = ""
            precedent.extraction_quality = quality
            precedent.quality_score = _court_weight_score(_clean(quality.get("court_weight"), 40))
            precedent.rag_text = "\n".join(chunk_text for _, chunk_text, _ in chunks)

            await db.flush()
            await db.execute(delete(PrecedentChunk).where(PrecedentChunk.precedent_id == precedent.id))
            precedent_id = precedent.id
            await db.commit()

        pending_chunks.extend((precedent_id, chunk_type, chunk_text, weight) for chunk_type, chunk_text, weight in chunks)
        if len(pending_chunks) >= EMBEDDING_BATCH_SIZE:
            chunked += await _insert_chunk_batch(pending_chunks, skip_embeddings)
            pending_chunks = []

        imported += 1
        if imported % 25 == 0:
            print(f"imported={imported} chunks={chunked} skipped={skipped}")

    chunked += await _insert_chunk_batch(pending_chunks, skip_embeddings)

    async with AsyncSessionLocal() as db:
        precedent_count = await db.scalar(select(func.count(Precedent.id)))
        chunk_count = await db.scalar(select(func.count(PrecedentChunk.id)))
    print(f"done imported={imported} chunks={chunked} skipped={skipped} db_precedents={precedent_count} db_chunks={chunk_count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=str(PROJECT_ROOT / "data" / "crawling" / "structured_precedents_v2" / "precedents.json"),
    )
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-embeddings", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_precedents(Path(args.path), args.reset, args.limit, args.skip_embeddings))


if __name__ == "__main__":
    main()
