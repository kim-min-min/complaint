import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.complaint import (
    ReferenceAnalyzeResponse,
    ReferenceSearchRequest,
    SimilarPrecedentItem,
)
from services.charge_search_config import CANONICAL_CHARGES
from services.complaint_service import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from services.embedding_service import create_embedding, vector_literal

@dataclass(frozen=True)
class ReferenceAnalysis:
    charge_candidates: list[str] = field(default_factory=list)
    is_meaningful_case: bool = True
    invalid_reason: str = ""
    search_keywords: list[str] = field(default_factory=list)
    search_query: str = ""


def _dedupe_keywords(keywords: list[str]) -> list[str]:
    seen = set()
    results = []
    for keyword in keywords:
        cleaned = str(keyword or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)
    return results[:20]


def _normalize_charge_candidates(values: list[Any]) -> list[str]:
    canonical_set = set(CANONICAL_CHARGES)
    seen = set()
    results = []
    for value in values:
        cleaned = _normalize_search_text(str(value or "")).replace(" ", "")
        if cleaned not in canonical_set or cleaned in seen:
            continue
        seen.add(cleaned)
        results.append(cleaned)
        if len(results) >= 3:
            break
    return results


def _parse_reference_analysis(data: dict[str, Any], fallback_query: str) -> ReferenceAnalysis:
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("OpenAI 응답에 검색 정보가 없습니다.")
    text_value = ((choices[0].get("message") or {}).get("content") or "").strip()
    parsed = json.loads(text_value)
    if not isinstance(parsed, dict):
        raise ValueError("검색 정보 응답 형식이 올바르지 않습니다.")

    raw_keywords = parsed.get("search_keywords") or []
    raw_candidates = parsed.get("charge_candidates") or []
    search_query = _normalize_search_text(str(parsed.get("search_query") or fallback_query))
    return ReferenceAnalysis(
        charge_candidates=_normalize_charge_candidates(raw_candidates if isinstance(raw_candidates, list) else []),
        is_meaningful_case=bool(parsed.get("is_meaningful_case", True)),
        invalid_reason=_normalize_search_text(str(parsed.get("invalid_reason") or "")),
        search_keywords=_dedupe_keywords(raw_keywords if isinstance(raw_keywords, list) else []),
        search_query=search_query,
    )


async def infer_reference_query(payload: ReferenceSearchRequest) -> ReferenceAnalysis:
    fallback_query = _reference_query_text(payload, [], "")
    is_meaningful_case = len(_normalize_search_text(payload.incident_description)) >= 10
    if not is_meaningful_case:
        return ReferenceAnalysis(
            is_meaningful_case=False,
            invalid_reason="사건 내용이 너무 짧아 유사 판례를 찾기 어렵습니다.",
            search_query=fallback_query,
        )
    if not OPENAI_API_KEY:
        return ReferenceAnalysis(search_query=fallback_query)

    prompt = f"""
사용자가 입력한 사건 내용을 판례 검색에 사용할 JSON으로 정리하세요.

원칙:
- 사용자가 입력하지 않은 사실은 추측하지 마세요.
- 법적 결론이나 유죄 가능성을 단정하지 마세요.
- charge_candidates는 아래 허용 죄명 목록에 있는 값만 그대로 사용하세요.
- charge_candidates는 입력 사실과 직접 연결되는 죄명만 1~3개 고르세요.
- 물건 이름, 장소, 피해품이 비슷하다는 이유만으로 행위 구조가 다른 죄명을 고르지 마세요.
- search_query는 죄명명이 아니라 구체적 사실관계 중심으로 한 문장 작성하세요.
- search_keywords는 판례 검색에 도움이 되는 사실 단서만 작성하세요.

허용 죄명 목록:
{", ".join(CANONICAL_CHARGES)}

반드시 JSON만 출력하세요.
{{
  "is_meaningful_case": true,
  "invalid_reason": "",
  "charge_candidates": ["허용 죄명 목록 중 직접 연결되는 죄명"],
  "search_keywords": ["핵심 사실 단서"],
  "search_query": "판례 검색용 사실관계 한 문장"
}}

사용자 입력:
발생 일시: {payload.incident_date}
발생 장소: {payload.incident_location}
사건 내용: {payload.incident_description}
증거 자료: {payload.evidence_summary}
""".strip()

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "당신은 형사 판례 검색을 위해 사건 사실을 구조화하는 보조자입니다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=request_body,
        )
        response.raise_for_status()
        data = response.json()

    return _parse_reference_analysis(data, fallback_query)


def _reference_query_text(payload: ReferenceSearchRequest, search_keywords: list[str], search_query: str) -> str:
    return " ".join(
        [
            search_query,
            payload.incident_location,
            payload.incident_description,
            " ".join(search_keywords),
        ]
    ).strip()


def _normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _best_excerpt(row, terms: list[str], max_length: int = 260) -> str:
    candidates = [
        _normalize_search_text(str(row.chunk_text or "")),
        _normalize_search_text(str(row.fact_context or "")),
        _normalize_search_text(str(row.holding or "")),
    ]
    text_value = next((candidate for candidate in candidates if candidate), "")
    if len(text_value) <= max_length:
        return text_value

    hit_positions = [text_value.find(term) for term in terms if term and text_value.find(term) >= 0]
    if hit_positions:
        center = min(hit_positions)
        start = max(0, center - 70)
        end = min(len(text_value), start + max_length)
        start = max(0, end - max_length)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text_value) else ""
        return f"{prefix}{text_value[start:end].rstrip()}{suffix}"
    return text_value[:max_length].rstrip() + "..."


def _precedent_title(row) -> str:
    label = _normalize_search_text(str(getattr(row, "primary_charge", "") or row.primary_case_name or "판례"))
    court = _normalize_search_text(str(getattr(row, "court_name", "") or ""))
    date = _normalize_search_text(str(getattr(row, "verdict_date", "") or ""))
    number = _normalize_search_text(str(getattr(row, "case_number", "") or ""))
    pieces = [piece for piece in [label, court, date] if piece]
    title = " · ".join(pieces) or "판례"
    if number:
        title = f"{title} ({number})"
    return title


def _primary_name(label: str) -> str:
    return label.removesuffix("죄")


def _charge_filter_sql(charge_labels: list[str]) -> tuple[str, dict[str, str]]:
    labels = [label for label in charge_labels[:4] if label]
    if not labels:
        return "", {}

    clauses = []
    params = {}
    for index, label in enumerate(labels):
        primary_name = _primary_name(label)
        label_key = f"label_{index}"
        primary_key = f"primary_{index}"
        params[label_key] = label
        params[primary_key] = primary_name
        clauses.append(
            f"(p.primary_charge = :{label_key} OR p.primary_case_name = :{primary_key} OR jsonb_exists(p.charges, :{label_key}))"
        )
    return "AND (" + " OR ".join(clauses) + ")", params


async def _search_similar_precedents(
    db: AsyncSession,
    query_text: str,
    terms: list[str],
    charge_labels: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    query_embedding = await create_embedding(query_text)
    charge_filter, charge_params = _charge_filter_sql(charge_labels or [])
    result = await db.execute(
        text(
            f"""
            SELECT
                p.id,
                p.source_id,
                p.source_url,
                p.case_number,
                p.case_name,
                p.primary_case_name,
                p.primary_charge,
                p.charges,
                p.court_name,
                p.verdict_date,
                p.holding,
                p.summary,
                p.fact_context,
                p.reasoning_excerpt,
                fact_pc.text AS chunk_text,
                fact_pc.text AS fact_text,
                issue_pc.text AS issue_text,
                outcome_pc.text AS outcome_text,
                fact_pc.embedding <=> CAST(:query_embedding AS vector) AS distance
            FROM precedent_chunks fact_pc
            JOIN precedents p ON p.id = fact_pc.precedent_id
            LEFT JOIN precedent_chunks issue_pc
              ON issue_pc.precedent_id = p.id AND issue_pc.chunk_type = 'issue'
            LEFT JOIN precedent_chunks outcome_pc
              ON outcome_pc.precedent_id = p.id AND outcome_pc.chunk_type = 'outcome'
            WHERE fact_pc.chunk_type = 'fact'
            {charge_filter}
            ORDER BY distance ASC
            LIMIT :limit
            """
        ),
        {
            "query_embedding": vector_literal(query_embedding),
            "limit": limit,
            **charge_params,
        },
    )
    rows = result.fetchall()
    return [
        {
            "id": str(row.source_id),
            "title": _precedent_title(row),
            "source_url": str(row.source_url or ""),
            "summary": _best_excerpt(row, terms),
            "primary_charge": str(row.primary_charge or ""),
            "case_charges": row.charges if isinstance(row.charges, list) else [],
            "issue": _normalize_search_text(str(row.issue_text or row.holding or "")),
            "fact": _normalize_search_text(str(row.fact_text or row.fact_context or "")),
            "outcome": _normalize_search_text(str(row.outcome_text or row.summary or "")),
            "distance": float(row.distance or 0),
        }
        for row in rows
    ]


def _parse_precedent_guidance_items(data: dict[str, Any]) -> dict[str, dict[str, str]]:
    choices = data.get("choices") or []
    if not choices:
        return {}
    text_value = ((choices[0].get("message") or {}).get("content") or "").strip()
    parsed = json.loads(text_value)
    items = parsed.get("items") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        return {}

    results = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        precedent_id = str(item.get("precedent_id") or "").strip()
        precedent_issue = _normalize_search_text(str(item.get("precedent_issue") or ""))
        issue_question = _normalize_search_text(str(item.get("issue_question") or item.get("question") or ""))
        if not precedent_id or not precedent_issue or not issue_question:
            continue
        results[precedent_id] = {
            "precedent_id": precedent_id,
            "precedent_issue": precedent_issue,
            "issue_question": issue_question,
            "selection_reason": _normalize_search_text(str(item.get("relevance_reason") or item.get("selection_reason") or "")),
            "how_to_use_in_complaint": _normalize_search_text(str(item.get("how_to_use_in_complaint") or "")),
        }
    return results


def _fallback_selected_precedent(precedent: dict[str, Any]) -> dict[str, str]:
    issue = _normalize_search_text(precedent["issue"] or "이 판례에서 다룬 핵심 쟁점")
    return {
        "precedent_id": precedent["id"],
        "precedent_issue": issue,
        "issue_question": f"'{issue}'와 관련해 현재 사건에서 추가로 설명할 사실이 있나요?",
        "selection_reason": "fact 유사도 기준으로 가장 가까운 판례입니다.",
        "how_to_use_in_complaint": "고소이유에서는 사용자 사건의 구체적 사실관계와 참고판례의 핵심 쟁점이 연결되는 부분을 조심스럽게 설명합니다.",
    }


def _to_similar_precedent_item(
    precedent: dict[str, Any],
    selected_precedent: dict[str, str],
) -> SimilarPrecedentItem:
    return SimilarPrecedentItem(
        id=precedent["id"],
        title=precedent["title"],
        charge=precedent.get("matched_charge") or precedent["primary_charge"],
        source_url=precedent["source_url"],
        issue=selected_precedent["precedent_issue"],
        summary=precedent["summary"],
        question=selected_precedent["issue_question"],
        selection_reason=selected_precedent["selection_reason"],
        how_to_use_in_complaint=selected_precedent["how_to_use_in_complaint"],
    )


async def _build_precedent_guidance_batch(
    payload: ReferenceSearchRequest,
    fact_summary: str,
    precedents: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    if not OPENAI_API_KEY or not precedents:
        return {}

    precedent_lines = []
    for index, precedent in enumerate(precedents[:3], start=1):
        precedent_lines.append(
            {
                "precedent_id": precedent["id"],
                "rank": index,
                "title": precedent["title"],
                "primary_charge": precedent.get("primary_charge", ""),
                "case_charges": precedent.get("case_charges", []),
                "issue": precedent["issue"][:500],
                "fact": precedent["fact"][:700],
                "outcome": precedent["outcome"][:400],
                "summary": precedent["summary"][:500],
            }
        )

    prompt = f"""
당신은 유사 판례의 쟁점을 현재 사건에 적용해 보완 질문을 만드는 보조자입니다.

질문 작성 기준:
- 판례 쟁점을 먼저 더 일반적인 사실 쟁점으로 바꾸세요.
- 일반화한 쟁점을 사용자 사건에 적용하세요.
- 질문은 사용자가 직접 겪은 말, 행동, 상황 중 고소이유를 보강할 사실을 묻는 문장으로 작성하세요.
- 판례의 물건명, 금액, 날짜, 표현을 질문에 복사하지 마세요.
- 사용자 사건에 없는 구체 사실을 질문에 넣지 마세요.
- 법률 판단이나 죄명 성립 여부를 묻지 마세요.
- 부수 정황보다 판례 쟁점과 직접 연결되는 사실을 우선 질문하세요.
- 예/아니오로 답할 수 있는 질문이 아니라, 구체적 사실을 묻는 질문으로 작성하세요.
- 질문은 짧게 1개만 작성하세요.

반드시 JSON만 출력하세요.
{{
  "items": [
    {{
      "precedent_id": "판례 id",
      "precedent_issue": "판례에서 실제로 다룬 핵심 쟁점",
      "issue_question": "사용자에게 물어볼 짧은 사실 질문 1개",
      "relevance_reason": "현재 사건과 이 판례 쟁점이 연결되는 이유",
      "how_to_use_in_complaint": "고소장 고소이유에 반영할 방향"
    }}
  ]
}}

사용자 사건:
발생 일시: {payload.incident_date}
발생 장소: {payload.incident_location}
사건 내용: {payload.incident_description}
증거 자료: {payload.evidence_summary}

검색용 사건 요약:
{fact_summary}

유사 판례:
{json.dumps(precedent_lines, ensure_ascii=False)}
""".strip()

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "당신은 유사 판례 쟁점을 사용자 답변용 사실 질문으로 바꾸는 보조자입니다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=request_body,
        )
        response.raise_for_status()
        data = response.json()

    return _parse_precedent_guidance_items(data)


def _precedent_charge_key(precedent: dict[str, Any]) -> str:
    return (
        _normalize_search_text(str(precedent.get("matched_charge") or ""))
        or _normalize_search_text(str(precedent.get("primary_charge") or ""))
        or _normalize_search_text(str(precedent.get("title") or ""))
        or str(precedent.get("id") or "")
    )


def _with_matched_charges(
    precedents: list[dict[str, Any]],
    charge_candidates: list[str],
) -> list[dict[str, Any]]:
    if not charge_candidates:
        return precedents

    results = []
    for precedent in precedents:
        case_charges = set(precedent.get("case_charges") or [])
        primary_charge = precedent.get("primary_charge") or ""
        matched_charge = next(
            (
                charge
                for charge in charge_candidates
                if charge == primary_charge or charge in case_charges
            ),
            primary_charge,
        )
        results.append({**precedent, "matched_charge": matched_charge})
    return results


def _representative_precedents(precedents: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    if not precedents:
        return []

    first_key = _precedent_charge_key(precedents[0])
    if first_key and all(_precedent_charge_key(precedent) == first_key for precedent in precedents):
        return [precedents[0]]

    representatives = []
    seen_keys = set()
    for precedent in precedents:
        key = _precedent_charge_key(precedent)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        representatives.append(precedent)
        if len(representatives) >= limit:
            break
    return representatives


async def _build_representative_precedents(
    db: AsyncSession,
    payload: ReferenceSearchRequest,
    fact_summary: str,
    terms: list[str],
    charge_candidates: list[str],
) -> list[SimilarPrecedentItem]:
    selected_items: list[SimilarPrecedentItem] = []
    seen_ids = set()
    searched_precedents = await _search_similar_precedents(
        db,
        fact_summary,
        terms,
        charge_candidates,
        limit=5,
    )
    if not searched_precedents and charge_candidates:
        searched_precedents = await _search_similar_precedents(db, fact_summary, terms, limit=5)

    searched_precedents = _with_matched_charges(searched_precedents, charge_candidates)
    representative_precedents = _representative_precedents(searched_precedents, limit=3)
    guidance_by_id = await _build_precedent_guidance_batch(payload, fact_summary, representative_precedents)

    for precedent in representative_precedents:
        selected_precedent = guidance_by_id.get(precedent["id"])
        if not selected_precedent:
            selected_precedent = _fallback_selected_precedent(precedent)
        if precedent["id"] in seen_ids:
            continue
        seen_ids.add(precedent["id"])
        selected_items.append(_to_similar_precedent_item(precedent, selected_precedent))

    return selected_items


async def analyze_reference_points(
    db: AsyncSession,
    payload: ReferenceSearchRequest,
    analysis: ReferenceAnalysis,
    usage_limit: int,
    usage_used: int,
    usage_remaining: int,
) -> ReferenceAnalyzeResponse:
    fact_summary = analysis.search_query or _reference_query_text(payload, analysis.search_keywords, "")
    if not analysis.is_meaningful_case or not fact_summary:
        return ReferenceAnalyzeResponse(
            is_meaningful_case=analysis.is_meaningful_case,
            invalid_reason=analysis.invalid_reason,
            fact_summary=fact_summary,
            similar_precedent=None,
            similar_precedents=[],
            usage_limit=usage_limit,
            usage_used=usage_used,
            usage_remaining=usage_remaining,
        )

    terms = _dedupe_keywords(analysis.search_keywords)
    similar_precedents = await _build_representative_precedents(
        db,
        payload,
        fact_summary,
        terms,
        analysis.charge_candidates,
    )
    similar_precedent = similar_precedents[0] if similar_precedents else None

    return ReferenceAnalyzeResponse(
        is_meaningful_case=analysis.is_meaningful_case,
        invalid_reason=analysis.invalid_reason,
        fact_summary=fact_summary,
        similar_precedent=similar_precedent,
        similar_precedents=similar_precedents,
        usage_limit=usage_limit,
        usage_used=usage_used,
        usage_remaining=usage_remaining,
    )
