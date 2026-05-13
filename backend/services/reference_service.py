import json
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.complaint import ChargeCandidateItem, LegalReferenceItem, ReferenceSearchRequest
from services.complaint_service import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from services.embedding_service import create_embedding, vector_literal

KNOWN_CHARGES = [
    "폭행죄", "상해죄", "사기죄", "명예훼손죄", "모욕죄", "횡령죄", "배임죄", "절도죄",
    "협박죄", "주거침입죄", "업무방해죄", "공무집행방해죄", "강도죄", "강간죄", "감금죄",
    "특수상해죄", "강도상해죄", "살인미수죄", "유사강간죄", "강제추행죄", "준강간죄",
    "준강제추행죄", "강간등상해치상죄", "강간등살인치사죄", "미성년자등에대한간음죄",
    "업무상위력등에의한간음죄", "미성년자에대한간음추행죄", "강도강간죄",
    "카메라등이용촬영죄", "카메라등이용촬영물반포등죄", "통신매체이용음란죄",
    "스토킹범죄의처벌등에관한법률위반",
]

CHARGE_REQUIREMENTS = {
    "폭행죄": ["사람의 신체에 대한 유형력 행사", "상해 결과가 없어도 가능"],
    "상해죄": ["사람의 신체 훼손 또는 생리기능 장애", "진단서, 치료, 출혈, 골절, 상처 등 상해 결과"],
    "특수상해죄": ["상해 결과", "위험한 물건 사용 또는 단체·다중의 위력"],
    "강도죄": ["폭행 또는 협박", "재물 강취 또는 재산상 이익 취득"],
    "강도상해죄": ["강도 행위", "그 과정에서 피해자 상해 발생"],
    "살인미수죄": ["사망 가능성이 큰 공격", "살해 고의 또는 사망을 의도한 정황", "사망하지 않음"],
    "협박죄": ["해악 고지", "상대방에게 공포심을 일으킬 정도의 구체성"],
    "감금죄": ["장소 이전 또는 이탈의 자유 제한", "일정 시간 벗어나지 못하게 함"],
    "강간죄": ["폭행 또는 협박", "상대방 의사에 반한 간음"],
    "유사강간죄": ["폭행 또는 협박", "구강·항문 등 신체 내부에 성기 삽입 또는 성기·항문에 신체 일부나 도구 삽입"],
    "강제추행죄": ["폭행 또는 협박", "상대방 의사에 반한 추행"],
    "준강간죄": ["심신상실 또는 항거불능 상태 이용", "간음"],
    "준강제추행죄": ["심신상실 또는 항거불능 상태 이용", "추행"],
    "강간등상해치상죄": ["강간·유사강간·강제추행·준강간·준강제추행 등", "상해 발생 또는 상해에 이르게 함"],
    "강간등살인치사죄": ["강간·유사강간·강제추행·준강간·준강제추행 등", "살해 또는 사망에 이르게 함"],
    "미성년자등에대한간음죄": ["미성년자 또는 심신미약자", "위계 또는 위력", "간음 또는 추행"],
    "업무상위력등에의한간음죄": ["업무·고용 등 보호 또는 감독 관계", "위계 또는 위력", "간음"],
    "미성년자에대한간음추행죄": ["미성년자 대상", "간음 또는 추행"],
    "강도강간죄": ["강도 행위", "강간"],
    "카메라등이용촬영죄": ["카메라 등 기계장치 이용", "성적 욕망 또는 수치심 유발 신체", "상대방 의사에 반한 촬영"],
    "카메라등이용촬영물반포등죄": ["카메라등이용촬영물 또는 복제물", "반포·판매·임대·제공 또는 공공연한 전시·상영"],
    "통신매체이용음란죄": ["통신매체 이용", "성적 욕망 유발 또는 만족 목적", "성적 수치심 또는 혐오감 유발 내용 도달"],
    "사기죄": ["기망행위", "착오", "재산 처분행위", "재산상 손해"],
    "횡령죄": ["타인 재물 보관자 지위", "반환 거부 또는 임의 처분"],
    "배임죄": ["타인의 사무 처리자 지위", "임무 위배", "재산상 손해"],
    "절도죄": ["타인의 재물", "동의 없는 절취", "불법영득 의사"],
    "명예훼손죄": ["공연성", "사실 또는 허위사실 적시", "사회적 평가 저하 가능성"],
    "모욕죄": ["공연성", "구체적 사실이 아닌 모욕적 표현"],
    "주거침입죄": ["사람의 주거 또는 관리 장소", "의사에 반한 침입"],
    "업무방해죄": ["업무 존재", "위계 또는 위력", "업무 방해 위험 또는 결과"],
    "공무집행방해죄": ["공무원의 적법한 직무집행", "폭행 또는 협박으로 방해"],
    "스토킹범죄의처벌등에관한법률위반": ["상대방 의사에 반한 접근·연락 등", "반복성 또는 지속성", "불안감 또는 공포심 유발"],
}

CHARGE_PRIMARY_NAMES = {
    "폭행죄": "폭행",
    "상해죄": "상해",
    "특수상해죄": "특수상해",
    "강도상해죄": "강도상해",
    "살인미수죄": "살인미수",
    "스토킹범죄의처벌등에관한법률위반": "스토킹",
}

EVIDENCE_KEYWORDS = {"진단서", "사진", "증거", "녹취", "캡처", "영수증", "병원", "이송", "치료"}

@dataclass(frozen=True)
class ReferenceAnalysis:
    candidates: list[dict[str, str]]
    is_meaningful_case: bool = True
    invalid_reason: str = ""
    search_keywords: list[str] = field(default_factory=list)
    search_query: str = ""
    fact_improvement_items: list[str] = field(default_factory=list)
    reason_improvement_items: list[str] = field(default_factory=list)


def _safe_id(label: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "-", label).strip("-")
    return value or "charge"


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


def _search_terms(keywords: list[str]) -> list[str]:
    return [
        keyword for keyword in _dedupe_keywords(keywords)
        if not any(evidence in keyword for evidence in EVIDENCE_KEYWORDS)
    ]


def _requirements_prompt() -> str:
    lines = []
    for label in KNOWN_CHARGES:
        elements = " / ".join(CHARGE_REQUIREMENTS.get(label, []))
        lines.append(f"- {label}: {elements}")
    return "\n".join(lines)


def _parse_reference_analysis(data: dict[str, Any]) -> ReferenceAnalysis:
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("OpenAI 응답에 죄명 후보가 없습니다.")
    text = ((choices[0].get("message") or {}).get("content") or "").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("죄명 후보 응답 형식이 올바르지 않습니다.")

    is_meaningful_case = bool(parsed.get("is_meaningful_case", True))
    invalid_reason = str(parsed.get("invalid_reason") or "").strip()
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("죄명 후보 응답 형식이 올바르지 않습니다.")

    results = []
    for item in candidates[:4]:
        if isinstance(item, str):
            label = item.strip()
            reason = "구성요건표를 기준으로 검토할 수 있는 후보입니다."
        elif isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            reason = str(item.get("reason") or "구성요건표를 기준으로 검토할 수 있는 후보입니다.").strip()
        else:
            continue
        if label not in KNOWN_CHARGES:
            continue
        results.append({
            "label": label,
            "reason": reason,
        })
    raw_keywords = parsed.get("search_keywords") or []
    search_keywords = _dedupe_keywords(raw_keywords if isinstance(raw_keywords, list) else [])
    search_query = str(parsed.get("search_query") or "").strip()
    raw_fact_items = parsed.get("fact_improvement_items") or []
    raw_reason_items = parsed.get("reason_improvement_items") or []
    return ReferenceAnalysis(
        is_meaningful_case=is_meaningful_case,
        invalid_reason=invalid_reason,
        candidates=results,
        search_keywords=search_keywords,
        search_query=search_query,
        fact_improvement_items=_dedupe_keywords(raw_fact_items if isinstance(raw_fact_items, list) else [])[:5],
        reason_improvement_items=_dedupe_keywords(raw_reason_items if isinstance(raw_reason_items, list) else [])[:5],
    )


async def infer_charge_candidates(payload: ReferenceSearchRequest) -> ReferenceAnalysis:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

    prompt = f"""
사용자가 입력한 사건 내용을 분석하여 고소장 초안 작성에 필요한 참고 정보를 JSON으로 출력하세요.

역할:
- 죄명 후보는 확정 판단이 아니라 참고용 후보로만 제시합니다.
- 사용자가 입력하지 않은 사실은 추측하지 않습니다.
- 입력 내용이 짧거나 불완전하더라도 실제 피해를 호소하는 내용이면 의미 있는 입력으로 봅니다.
- 정보가 부족한 경우에도 초안 생성을 막지 말고, 부족한 내용은 보완 포인트로 안내합니다.

의미 없는 입력 처리:
- 명백한 장난, 테스트, 무작위 문자, 반복 문자처럼 사건 내용으로 볼 수 없는 경우에만 is_meaningful_case를 false로 출력합니다.
- 그 외에는 is_meaningful_case를 true로 출력합니다.

죄명 후보 처리:
- 아래 구성요건표에 있는 죄명만 후보로 사용합니다.
- 구성요건에 맞지 않는 죄명은 제외합니다.
- 복수 죄명이 검토 가능하면 복수 후보를 제시합니다.
- 단어가 비슷하다는 이유만으로 가중범이나 특수범을 제시하지 않습니다.

검색 정보:
- search_keywords와 search_query는 판례 검색에 필요한 핵심 사건 내용을 기준으로 작성합니다.
- 증거자료 명칭 자체를 핵심 검색어로 삼지 않습니다.

보완 포인트:
- fact_improvement_items에는 범죄사실을 더 구체화하기 위해 필요한 내용을 적습니다.
- reason_improvement_items에는 고소이유를 더 구체화하기 위해 필요한 내용을 적습니다.

반드시 아래 JSON 형식만 출력하세요.

구성요건표:
{_requirements_prompt()}

출력:
{{
  "is_meaningful_case":true,
  "invalid_reason":"",
  "candidates":[{{"label":"죄명","reason":"후보로 볼 수 있는 이유를 짧게 작성"}}],
  "search_keywords":["판례 검색에 사용할 핵심 단서"],
  "search_query":"판례 검색용으로 정리한 한 문장",
  "fact_improvement_items":["범죄사실 보완을 위해 사용자가 추가로 적으면 좋은 내용"],
  "reason_improvement_items":["고소이유 보완을 위해 사용자가 추가로 적으면 좋은 내용"]
}}

후보가 없는 경우 출력 예시:
{{
  "is_meaningful_case":false,
  "invalid_reason":"사건 내용으로 보기 어려운 입력입니다.",
  "candidates":[],
  "search_keywords":[],
  "search_query":"",
  "fact_improvement_items":["사건 내용을 문장으로 입력하면 죄명 후보를 검토할 수 있습니다."],
  "reason_improvement_items":["고소하게 된 이유를 입력하면 고소이유 작성에 도움이 됩니다."]
}}

입력:
발생 일시: {payload.incident_date}
발생 장소: {payload.incident_location}
사건 내용: {payload.incident_description}
증거 자료: {payload.evidence_summary}
처벌 의사: {payload.requested_punishment}
""".strip()

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "당신은 대한민국 형사 고소장 작성을 위한 참고 후보를 구조화하는 보조자입니다."},
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

    return _parse_reference_analysis(data)


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


def _reference_title(row) -> str:
    case_name = _normalize_search_text(str(row.case_name or "판례"))
    if len(case_name) > 46:
        case_name = case_name[:46].rstrip() + "..."
    return f"{case_name} ({row.case_number})"


def _primary_name(label: str) -> str:
    return CHARGE_PRIMARY_NAMES.get(label) or label.removesuffix("죄")


def _empty_reference_results(charge_labels: list[str]) -> list[ChargeCandidateItem]:
    return [
        ChargeCandidateItem(id=_safe_id(label), label=label, references=[])
        for label in charge_labels
    ]


async def _search_references_for_charge(
    db: AsyncSession,
    label: str,
    query_text: str,
    terms: list[str],
) -> list[LegalReferenceItem]:
    primary_name = _primary_name(label)
    if not primary_name:
        return []

    query_embedding = await create_embedding(query_text)
    result = await db.execute(
        text(
            """
            WITH ranked_precedents AS (
                SELECT DISTINCT ON (p.id)
                    p.id,
                    p.source_id,
                    p.case_number,
                    p.case_name,
                    p.primary_case_name,
                    p.holding,
                    p.fact_context,
                    pc.text AS chunk_text,
                    pc.chunk_type,
                    (pc.embedding <=> CAST(:query_embedding AS vector)) AS distance,
                    pc.weight
                FROM precedent_chunks pc
                JOIN precedents p ON p.id = pc.precedent_id
                WHERE pc.chunk_type = 'fact'
                  AND p.primary_case_name = :primary_name
                ORDER BY p.id, pc.embedding <=> CAST(:query_embedding AS vector)
            )
            SELECT *
            FROM ranked_precedents
            ORDER BY distance ASC, weight DESC
            LIMIT 3
            """
        ),
        {
            "primary_name": primary_name,
            "query_embedding": vector_literal(query_embedding),
        },
    )
    return [
        LegalReferenceItem(
            id=str(row.source_id),
            title=_reference_title(row),
            summary=_best_excerpt(row, terms),
        )
        for row in result.fetchall()
    ]


async def search_references(
    db: AsyncSession,
    payload: ReferenceSearchRequest,
    charge_labels: list[str],
    search_keywords: list[str],
    search_query: str,
) -> list[ChargeCandidateItem]:
    terms = _search_terms(search_keywords)
    query_text = _reference_query_text(payload, terms, search_query)
    if not query_text:
        return _empty_reference_results(charge_labels)

    try:
        refs_by_charge = {
            label: await _search_references_for_charge(db, label, query_text, terms)
            for label in charge_labels
        }
    except Exception:
        return _empty_reference_results(charge_labels)

    return [
        ChargeCandidateItem(
            id=_safe_id(label),
            label=label,
            references=refs_by_charge.get(label) or [],
        )
        for label in charge_labels
    ]
