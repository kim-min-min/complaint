import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.complaint import (
    ReferenceAnalyzeResponse,
    ReferenceGuidanceRequest,
    ReferenceSearchRequest,
    SimilarPrecedentItem,
)
from services.charge_search_config import CANONICAL_CHARGES
from services.complaint_service import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from services.embedding_service import create_embedding, vector_literal


SEARCH_CANDIDATE_LIMIT = 10
RERANK_INPUT_LIMIT = 10
DISPLAY_PRECEDENT_LIMIT = 3


@dataclass(frozen=True)
class ReferenceAnalysis:
    charge_candidates: list[str] = field(default_factory=list)
    is_meaningful_case: bool = True
    invalid_reason: str = ""
    search_keywords: list[str] = field(default_factory=list)
    search_query: str = ""


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
- search_query는 죄명명이나 법률요건이 아니라 사용자 사건의 구체적 사실 구조를 한 문장으로 작성하세요.
- search_query에는 사건 유형, 상대방이 제안하거나 약속한 내용, 금전을 요구한 명목, 사용자가 한 행동, 이후 이행되지 않은 내용을 최대한 유지하세요.
- 사용자 사건의 구체적 행위와 경위를 추상적인 법률 표현으로 뭉뚱그리지 마세요.
- search_keywords는 법률용어보다 사용자 사건에 나온 구체적 사실 단서 중심으로 작성하세요.

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

    parsed = _parse_reference_analysis(data, fallback_query)
    return parsed


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
    similar_precedents = await _search_reference_precedents(
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


async def build_precedent_guidance(request: ReferenceGuidanceRequest) -> SimilarPrecedentItem:
    fact_summary = request.fact_summary or _reference_query_text(request, [], "")
    precedent_data = _precedent_item_to_guidance_input(request.precedent)
    guidance_by_id = await _build_precedent_guidance_batch(request, fact_summary, [precedent_data])
    selected_precedent = guidance_by_id.get(request.precedent.id) or _fallback_selected_precedent(precedent_data)
    return _to_similar_precedent_item(precedent_data, selected_precedent)


async def _search_reference_precedents(
    db: AsyncSession,
    payload: ReferenceSearchRequest,
    fact_summary: str,
    terms: list[str],
    charge_candidates: list[str],
) -> list[SimilarPrecedentItem]:
    def unique_precedents(precedents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        seen_ids = set()
        for precedent in precedents:
            precedent_id = precedent.get("id")
            if precedent_id in seen_ids:
                continue
            seen_ids.add(precedent_id)
            results.append(precedent)
            if len(results) >= SEARCH_CANDIDATE_LIMIT:
                break
        return results

    searched_precedents = await _search_similar_precedents(
        db,
        fact_summary,
        terms,
        charge_candidates,
    )
    unique_results = unique_precedents(searched_precedents)
    reranked_results = await _rerank_precedents(payload, fact_summary, unique_results)
    return [_to_precedent_search_item(precedent) for precedent in reranked_results]


async def _search_similar_precedents(
    db: AsyncSession,
    query_text: str,
    terms: list[str],
    charge_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    query_embedding = await create_embedding(query_text)
    charge_filter, charge_params = _charge_filter_sql(charge_labels or [])
    await db.execute(text("SET LOCAL enable_indexscan = off"))
    await db.execute(text("SET LOCAL enable_bitmapscan = off"))
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
            "limit": SEARCH_CANDIDATE_LIMIT,
            **charge_params,
        },
    )
    rows = result.fetchall()
    precedents = [
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
    return precedents


async def _rerank_precedents(
    payload: ReferenceSearchRequest,
    fact_summary: str,
    precedents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not OPENAI_API_KEY or len(precedents) <= DISPLAY_PRECEDENT_LIMIT:
        return precedents[:DISPLAY_PRECEDENT_LIMIT]

    candidates = [
        {
            "id": precedent["id"],
            "title": precedent["title"],
            "issue": precedent.get("issue", "")[:250],
            "fact": precedent.get("fact", "")[:450],
        }
        for precedent in precedents[:RERANK_INPUT_LIMIT]
    ]
    candidate_ids = [candidate["id"] for candidate in candidates]

    prompt = f"""
사용자 사건과 후보 판례의 사실관계가 가까운 순서로 후보 판례 id를 정렬하세요.

기준:
- 죄명보다 사실 구조의 유사성을 우선하세요.
- 사용자 사건의 핵심 행위, 상대방의 설명이나 약속, 사용자가 한 행동, 이후 이행 경위와 직접 연결되는 판례를 우선하세요.
- 추상적인 법률 쟁점이 비슷한 판례보다 구체적인 사실 전개가 비슷한 판례를 우선하세요.
- 후보 판례에 없는 사실을 추측하지 마세요.
- 후보에 없는 id를 만들지 마세요.

반드시 JSON만 출력하세요.
{{
  "ranked_ids": ["가장 유사한 판례 id", "다음 판례 id", "다음 판례 id"]
}}

사용자 사건:
발생 일시: {payload.incident_date}
발생 장소: {payload.incident_location}
사건 내용: {payload.incident_description}
증거 자료: {payload.evidence_summary}

검색용 사건 요약:
{fact_summary}

후보 판례:
{json.dumps(candidates, ensure_ascii=False)}
""".strip()

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "당신은 후보 판례를 사실관계 유사도 기준으로 재정렬하는 보조자입니다."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.0,
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

    ranked_ids = _parse_reranked_ids(data, candidate_ids)
    by_id = {precedent["id"]: precedent for precedent in precedents}
    reranked = [by_id[precedent_id] for precedent_id in ranked_ids if precedent_id in by_id]
    for precedent in precedents:
        if precedent["id"] not in ranked_ids:
            reranked.append(precedent)
        if len(reranked) >= DISPLAY_PRECEDENT_LIMIT:
            break

    return reranked[:DISPLAY_PRECEDENT_LIMIT]


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
당신은 사용자의 사건 내용과 사용자가 선택한 판례 1개를 비교해, 고소장에 필요한 추가 사실 질문을 만드는 보조자입니다.

기준:
- 질문은 2~3개만 작성하세요.
- 일시, 장소, 사건 관련자의 말과 행동, 행위 방법, 피해 발생 과정, 피해 결과, 사건 전후 사정이 더 구체화될 필요가 있으면 질문하세요.
- 선택한 판례의 주요 쟁점을 확인하고, 현재 사건에 적용 가능성이 있는 사실 요소가 있으면 그 부분을 질문으로 바꾸어 물으세요.
- 법률 판단이나 결론을 사용자에게 묻지 말고, 사용자가 직접 겪은 구체적 사실을 묻는 문장으로 작성하세요.
- 질문 문장에서는 '저는', '제가', '저에게'를 쓰지 말고, '본인', '당신', '사용자' 중 자연스러운 표현으로 물으세요.
- 질문은 막연한 기억이나 감상을 묻지 말고, 누가, 언제, 어디서, 무엇을, 어떻게 했는지 확인하는 문장으로 작성하세요.
- 감정이나 처벌 의사 자체를 묻는 질문은 피하세요.
- 사용자가 말하지 않은 사실을 단정해서 전제로 삼지 말고, 예/아니오 질문은 피하세요.

반드시 JSON만 출력하세요.
{{
  "items": [
    {{
      "precedent_id": "판례 id",
      "precedent_issue": "선택한 판례의 쟁점",
      "missing_fact_points": [
        "사용자 사건에서 빠져 있거나 부족한 핵심 사실관계"
      ],
      "generalized_issue": "현재 사건에서 확인할 사실 요소",
      "issue_questions": [
        "사용자에게 물어볼 구체적 사실 질문 1",
        "사용자에게 물어볼 구체적 사실 질문 2"
      ],
      "relevance_reason": "선택한 판례와 현재 사건이 연결되는 이유",
      "how_to_use_in_complaint": "답변을 범죄사실 또는 고소이유에 반영할 방향"
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

선택한 판례:
{json.dumps(precedent_lines, ensure_ascii=False)}
""".strip()

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "당신은 형사 고소장에 필요한 추가 사실을 사용자 질문으로 정리하는 보조자입니다."},
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

    parsed = _parse_precedent_guidance_items(data)
    return parsed


def _to_precedent_search_item(precedent: dict[str, Any]) -> SimilarPrecedentItem:
    return SimilarPrecedentItem(
        id=precedent["id"],
        title=precedent["title"],
        charge=precedent.get("matched_charge") or precedent.get("primary_charge", ""),
        charges=precedent.get("case_charges", []),
        source_url=precedent.get("source_url", ""),
        issue=precedent.get("issue", ""),
        summary=precedent.get("summary", ""),
        fact=precedent.get("fact", ""),
        outcome=precedent.get("outcome", ""),
    )


def _precedent_item_to_guidance_input(precedent: SimilarPrecedentItem) -> dict[str, Any]:
    case_charges = precedent.charges or ([precedent.charge] if precedent.charge else [])
    return {
        "id": precedent.id,
        "title": precedent.title,
        "primary_charge": precedent.charge,
        "case_charges": case_charges,
        "source_url": precedent.source_url,
        "issue": precedent.issue,
        "fact": precedent.fact or precedent.summary,
        "outcome": precedent.outcome,
        "summary": precedent.summary,
    }


def _to_similar_precedent_item(
    precedent: dict[str, Any],
    selected_precedent: dict[str, str],
) -> SimilarPrecedentItem:
    return SimilarPrecedentItem(
        id=precedent["id"],
        title=precedent["title"],
        charge=precedent.get("matched_charge") or precedent["primary_charge"],
        charges=precedent.get("case_charges", []),
        source_url=precedent["source_url"],
        issue=selected_precedent["precedent_issue"],
        summary=precedent["summary"],
        fact=precedent.get("fact", ""),
        outcome=precedent.get("outcome", ""),
        question=selected_precedent["issue_question"],
        selection_reason=selected_precedent["selection_reason"],
        how_to_use_in_complaint=selected_precedent["how_to_use_in_complaint"],
    )


def _fallback_selected_precedent(precedent: dict[str, Any]) -> dict[str, str]:
    issue = _normalize_search_text(precedent["issue"] or "이 판례에서 다룬 핵심 쟁점")
    return {
        "precedent_id": precedent["id"],
        "precedent_issue": issue,
        "issue_question": f"'{issue}'와 관련해 현재 사건에서 추가로 설명할 사실이 있나요?",
        "selection_reason": "fact 유사도 기준으로 가장 가까운 판례입니다.",
        "how_to_use_in_complaint": "고소이유에서는 사용자 사건의 구체적 사실관계와 참고판례의 핵심 쟁점이 연결되는 부분을 조심스럽게 설명합니다.",
    }


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


def _parse_reranked_ids(data: dict[str, Any], candidate_ids: list[str]) -> list[str]:
    choices = data.get("choices") or []
    if not choices:
        return []
    text_value = ((choices[0].get("message") or {}).get("content") or "").strip()
    parsed = json.loads(text_value)
    ranked_ids = parsed.get("ranked_ids") if isinstance(parsed, dict) else None
    if not isinstance(ranked_ids, list):
        return []

    allowed = set(candidate_ids)
    results = []
    for value in ranked_ids:
        precedent_id = str(value or "").strip()
        if precedent_id in allowed and precedent_id not in results:
            results.append(precedent_id)
    return results


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
        issue_questions = _normalize_issue_questions(item)
        issue_question = "\n".join(f"{index}. {question}" for index, question in enumerate(issue_questions, start=1))
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


def _normalize_issue_questions(item: dict[str, Any]) -> list[str]:
    raw_questions = item.get("issue_questions")
    if isinstance(raw_questions, list):
        questions = [_normalize_search_text(str(value or "")) for value in raw_questions]
    else:
        fallback = item.get("issue_question") or item.get("question") or ""
        questions = [_normalize_search_text(str(fallback))]

    results = []
    for question in questions:
        if question and question not in results:
            results.append(question)
        if len(results) >= 3:
            break
    return results


def _reference_query_text(payload: ReferenceSearchRequest, search_keywords: list[str], search_query: str) -> str:
    return " ".join(
        [
            search_query,
            payload.incident_location,
            payload.incident_description,
            " ".join(search_keywords),
        ]
    ).strip()


def _charge_filter_sql(charge_labels: list[str]) -> tuple[str, dict[str, str]]:
    labels = [label for label in charge_labels[:4] if label]
    if not labels:
        return "", {}

    clauses = []
    params = {}
    for index, label in enumerate(labels):
        label_key = f"label_{index}"
        params[label_key] = label
        clauses.append(f"jsonb_exists(p.charges, :{label_key})")
    return "AND (" + " OR ".join(clauses) + ")", params


def _precedent_title(row) -> str:
    court = _normalize_search_text(str(getattr(row, "court_name", "") or ""))
    date = _normalize_search_text(str(getattr(row, "verdict_date", "") or ""))
    number = _normalize_search_text(str(getattr(row, "case_number", "") or ""))
    pieces = [piece for piece in [court, date] if piece]
    title = " · ".join(pieces) or "판례"
    if number:
        title = f"{title} ({number})"
    return title


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


def _normalize_search_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()
