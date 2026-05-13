import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from sqlalchemy import delete, func, select, text

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import AsyncSessionLocal  # noqa: E402
from models.precedent import Precedent, PrecedentChunk  # noqa: E402
from services.embedding_service import create_embedding, vector_literal  # noqa: E402


def _clean(value: object, limit: int | None = None) -> str:
    text_value = " ".join(str(value or "").split())
    return text_value[:limit] if limit else text_value


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_clean(item, 80) for item in value if _clean(item, 80)]
    if isinstance(value, str) and value.strip():
        return [_clean(value, 80)]
    return []


def _primary_case_name(case_name: str) -> str:
    cleaned = _clean(case_name, 500)
    depth = 0
    for index, char in enumerate(cleaned):
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        elif char == "·" and depth == 0:
            return cleaned[:index].strip().rstrip(",")[:200]
    return cleaned.strip().rstrip(",")[:200]


CHARGE_NAME_RULES = [
    ("살인미수죄", [r"살인미수"]),
    ("강도상해죄", [r"강도상해"]),
    ("강도죄", [r"강도"]),
    ("특수상해죄", [r"특수상해"]),
    ("상해치사죄", [r"상해치사"]),
    ("폭행치사죄", [r"(?<!성)폭행치사"]),
    ("폭행치상죄", [r"(?<!성)폭행치상"]),
    ("상해죄", [r"상해"]),
    ("폭행죄", [r"(?<!성)폭행"]),
    ("공무집행방해죄", [r"공무집행방해"]),
    ("무고죄", [r"무고"]),
    ("업무방해죄", [r"업무방해"]),
    ("명예훼손죄", [r"명예훼손"]),
    ("모욕죄", [r"모욕"]),
    ("사기죄", [r"사기"]),
    ("횡령죄", [r"횡령"]),
    ("배임죄", [r"배임"]),
    ("절도죄", [r"절도"]),
    ("협박죄", [r"협박"]),
    ("주거침입죄", [r"주거침입"]),
    ("감금죄", [r"감금"]),
    ("강간죄", [r"강간"]),
    ("성폭력범죄의처벌등에관한특례법위반", [r"성폭력범죄"]),
]


def _infer_charges_from_case_name(case_name: str) -> list[str]:
    text_value = _clean(case_name, 500)
    return [
        charge
        for charge, patterns in CHARGE_NAME_RULES
        if any(re.search(pattern, text_value) for pattern in patterns)
    ]


def _chunk_items(item: dict) -> list[tuple[str, str, float]]:
    fact_context = _clean(item.get("fact_summary") or item.get("fact_context"), 2500)
    return [("fact", fact_context, 1.0)] if fact_context else []


async def import_precedents(path: Path, reset: bool) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("판례 JSON은 리스트 형식이어야 합니다.")

    async with AsyncSessionLocal() as db:
        if reset:
            await db.execute(delete(PrecedentChunk))
            await db.execute(delete(Precedent))
            await db.commit()

        imported = 0
        chunked = 0
        for item in data:
            raw_source_id = _clean(item.get("prec_id") or item.get("source_id") or item.get("case_number"), 80)
            charge_name = _clean(item.get("charge"), 80)
            if not raw_source_id:
                continue
            source_id = _clean(f"{raw_source_id}:{charge_name}" if charge_name else raw_source_id, 80)

            existing = await db.execute(select(Precedent).where(Precedent.source_id == source_id))
            precedent = existing.scalar_one_or_none()
            if not precedent:
                precedent = Precedent(source_id=source_id)
                db.add(precedent)
            elif not reset:
                chunk_count = await db.scalar(
                    select(func.count(PrecedentChunk.id)).where(PrecedentChunk.precedent_id == precedent.id)
                )
                if chunk_count:
                    continue

            precedent.source = _clean(item.get("source") or "law.go.kr", 60)
            precedent.category = _clean(item.get("category") or item.get("primary_case_name"), 80) or "미분류"
            precedent.case_number = _clean(item.get("case_number"), 120) or source_id
            precedent.case_name = _clean(item.get("case_name"), 500) or precedent.case_number
            precedent.primary_case_name = _clean(item.get("primary_case_name"), 200) or _primary_case_name(precedent.case_name)
            precedent.court_name = _clean(item.get("court_name"), 160)
            precedent.verdict_date = _clean(item.get("verdict_date"), 40)
            precedent.verdict_type = _clean(item.get("verdict_type"), 120)
            precedent.case_type = _clean(item.get("case_type"), 80)
            precedent.charges = _as_list(item.get("charges")) or _as_list(item.get("charge")) or _infer_charges_from_case_name(precedent.case_name)
            precedent.keywords = _as_list(item.get("search_terms"))
            precedent.holding = ""
            precedent.summary = _clean(item.get("legal_point"))
            precedent.fact_context = _clean(item.get("fact_summary") or item.get("fact_context"))
            precedent.refs_articles = ""
            precedent.refs_cases = ""
            precedent.quality_score = 0
            precedent.rag_text = ""
            await db.flush()

            await db.execute(delete(PrecedentChunk).where(PrecedentChunk.precedent_id == precedent.id))
            for chunk_type, chunk_text, weight in _chunk_items(item):
                embedding = await create_embedding(chunk_text)
                await db.execute(
                    text(
                        """
                        INSERT INTO precedent_chunks (precedent_id, chunk_type, text, embedding, weight)
                        VALUES (:precedent_id, :chunk_type, :chunk_text, CAST(:embedding AS vector), :weight)
                        """
                    ),
                    {
                        "precedent_id": precedent.id,
                        "chunk_type": chunk_type,
                        "chunk_text": chunk_text,
                        "embedding": vector_literal(embedding),
                        "weight": weight,
                    },
                )
                chunked += 1

            imported += 1
            if imported % 10 == 0:
                await db.commit()
                print(f"imported={imported} chunks={chunked}")

        await db.commit()
        print(f"done imported={imported} chunks={chunked}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        default=str(PROJECT_ROOT / "data" / "crawling" / "precedents_v2" / "_combined.json"),
    )
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(import_precedents(Path(args.path), args.reset))


if __name__ == "__main__":
    main()
