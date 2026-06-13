import os
import re
import textwrap
from pathlib import Path

import httpx
from dotenv import load_dotenv

from schemas.complaint import ComplaintGenerateRequest

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("\ufeffOPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

SYSTEM_PROMPT = (
    "당신은 대한민국 형사 고소장 초안 작성 보조자입니다. "
    "사실을 꾸미지 않고, 사용자가 입력한 내용만 근거로 제출 검토 가능한 문서 형식의 한국어 초안을 작성합니다."
)

def _unknown(value: str, fallback: str = "미상") -> str:
    return value.strip() if value and value.strip() else fallback


def _attachments_text(payload: ComplaintGenerateRequest) -> str:
    if payload.attachments:
        return "\n".join(f"{idx}. {item}" for idx, item in enumerate(payload.attachments, 1))
    if payload.evidence_summary:
        return "1. 증거자료 사본"
    return "1. 증거자료 사본 (확보 시 제출)"


def _legal_references_text(payload: ComplaintGenerateRequest) -> str:
    if not payload.legal_references:
        return "사용자 선택 참고자료 없음"
    return "\n".join(f"- {item}" for item in payload.legal_references[:10])


def _purpose_text(payload: ComplaintGenerateRequest) -> str:
    charge = _unknown(payload.charge_name, "○○죄")
    return f"고소인은 피고소인을 {charge}로 고소하오니 처벌하여 주시기 바랍니다."


def _build_prompt(payload: ComplaintGenerateRequest) -> str:
    charge_instruction = (
        f"- 3. 고소취지는 반드시 다음 문장으로만 작성하세요: {_purpose_text(payload)}"
        if payload.charge_name and payload.charge_name.strip()
        else "- 3. 고소취지는 반드시 다음 문장으로만 작성하세요: 고소인은 피고소인을 ○○죄로 고소하오니 처벌하여 주시기 바랍니다."
    )
    return f"""
아래 사용자의 진술만 근거로 대한민국 형사 고소장 초안을 작성하세요.

출력 형식 규칙:
- 마크다운 기호(**, ###, ---)를 절대 쓰지 마세요.
- 아래 번호와 제목을 그대로 사용하세요: 고 소 장, 1. 고소인, 2. 피고소인, 3. 고소취지, 4. 범죄사실, 5. 고소이유, 6. 증거자료
- 사용자가 제공하지 않은 사실을 만들지 마세요.
- 모르는 개인정보는 '미상'으로만 표시하세요. '추후 보완 예정' 문구는 쓰지 마세요.
- AI가 죄명, 혐의명, 관련 법조를 새로 판단하거나 추가하지 마세요.
- 고소 죄명이 입력된 경우, 3. 고소취지와 5. 고소이유에서 그 죄명만 사용하세요.
- 고소 죄명과 다른 죄명 표현은 사용하지 마세요.
- 사용자가 입력한 표현에 다른 죄명처럼 보이는 단어가 있더라도, 이를 법적 죄명으로 단정하지 말고 구체적 행위 사실로 풀어 쓰세요.
{charge_instruction}

작성 규칙:
- 4. 범죄사실에는 사용자가 입력한 사실만 시간 순서에 맞게 정리하세요.
- 4. 범죄사실에서 빠진 사실을 추측하거나 만들어 쓰지 마세요.
- 5. 고소이유에는 범죄사실을 뒷받침하는 경위, 정황, 고소 동기, 피해 내용을 정리하세요.
- 판례의 적용 여부, 유죄 가능성, 범죄 성립 여부를 단정하지 마세요.
- “명백합니다”, “해당합니다”, “입증됩니다”, “보여줍니다”, “판례에 따르면” 같은 단정 표현을 쓰지 마세요.
- 관련 법조, 형법 조문, 특정 죄명 섹션은 만들지 마세요.
- 마지막 알림 문구는 쓰지 마세요. 서비스 화면에서 별도로 안내합니다.

보완 답변 및 참고판례 처리 규칙:
- 아래 “전 단계 보완 답변 및 선택 참고판례”에는 사용자의 보완 답변과 선택한 참고판례 정보가 함께 들어 있습니다.
- “고소이유 보완” 아래의 질문/답변은 사용자가 추가로 제공한 사실입니다.
- 질문/답변 내용은 5. 고소이유에 자연스럽게 반영하세요.
- 선택 참고판례 정보는 초안 본문에 작성하지 마세요.

입력 정보:
고소인 성명: {payload.complainant_name}
고소인 주민등록번호: {_unknown(payload.complainant_rrn)}
고소인 주소: {_unknown(payload.complainant_address)}
고소인 직업: {_unknown(payload.complainant_job)}
고소인 휴대폰 번호: {_unknown(payload.complainant_phone)}
피고소인 성명: {payload.accused_name}
피고소인 주민등록번호: {_unknown(payload.accused_rrn)}
피고소인 주소: {_unknown(payload.accused_address)}
피고소인 직업: {_unknown(payload.accused_job)}
피고소인 휴대폰 번호: {_unknown(payload.accused_phone)}
피고소인 기타사항: {_unknown(payload.accused_identifier)}
발생 일시: {_unknown(payload.incident_date)}
발생 장소: {_unknown(payload.incident_location)}
피해 내용: {payload.incident_description}
증거 자료: {_unknown(payload.evidence_summary, '별도 기재 없음')}
고소 죄명: {_unknown(payload.charge_name, '사용자 미입력')}

전 단계 보완 답변 및 선택 참고판례:
{_legal_references_text(payload)}
""".strip()


def _fallback_complaint(payload: ComplaintGenerateRequest) -> str:
    purpose = _purpose_text(payload)
    return textwrap.dedent(f"""
    고 소 장

    1. 고소인
    성명: {payload.complainant_name}
    주민등록번호: {_unknown(payload.complainant_rrn)}
    주소: {_unknown(payload.complainant_address)}
    직업: {_unknown(payload.complainant_job)}
    휴대폰 번호: {_unknown(payload.complainant_phone)}

    2. 피고소인
    성명: {payload.accused_name}
    주민등록번호: {_unknown(payload.accused_rrn)}
    주소: {_unknown(payload.accused_address)}
    직업: {_unknown(payload.accused_job)}
    휴대폰 번호: {_unknown(payload.accused_phone)}
    기타사항: {_unknown(payload.accused_identifier)}

    3. 고소취지
    {purpose}

    4. 범죄 사실
    발생 일시: {_unknown(payload.incident_date)}
    발생 장소: {_unknown(payload.incident_location)}
    {payload.incident_description}

    5. 고소이유
    피고소인의 행위 경위와 정황, 고소를 하게 된 동기와 사유는 위 범죄사실 기재 내용과 같습니다.
    {("※ 참고판례\n" + _legal_references_text(payload)) if payload.legal_references else ""}

    6. 증거자료
    {_unknown(payload.evidence_summary, '별도 기재 없음')}
    """).strip()


_CHARGE_PATTERNS = [
    "사기죄", "사기 혐의", "폭행죄", "폭행 혐의", "상해죄", "상해 혐의", "횡령죄", "횡령 혐의",
    "배임죄", "배임 혐의", "업무방해죄", "업무방해 혐의", "협박죄", "협박 혐의",
    "공갈죄", "공갈 혐의", "강요죄", "강요 혐의", "강도죄", "강도 혐의",
    "명예훼손죄", "명예훼손 혐의", "모욕죄", "모욕 혐의",
]


def _allowed_charge_tokens(value: str) -> set[str]:
    tokens = set()
    for part in re.split(r"[,/·\s]+", value or ""):
        cleaned = part.strip()
        if not cleaned:
            continue
        tokens.add(cleaned)
        tokens.add(cleaned.removesuffix("죄"))
    return tokens


def _sanitize_complaint_text(text: str, allowed_charge: str = "") -> str:
    allowed_charge = (allowed_charge or "").strip()
    allowed_tokens = _allowed_charge_tokens(allowed_charge)
    charge_replacements = {
        "사기죄": "피고소인의 행위",
        "사기 혐의": "피고소인의 행위",
        "사기 행위": "피고소인의 행위",
        "사기범행": "피고소인의 행위",
        "횡령죄": "피고소인의 행위",
        "횡령 혐의": "피고소인의 행위",
        "횡령 행위": "피고소인의 행위",
        "배임죄": "피고소인의 행위",
        "배임 혐의": "피고소인의 행위",
        "배임 행위": "피고소인의 행위",
        "업무방해죄": "피고소인의 행위",
        "업무방해 혐의": "피고소인의 행위",
        "업무방해 행위": "피고소인의 행위",
        "협박죄": "피고소인의 행위",
        "협박 혐의": "피고소인의 행위",
        "협박 행위": "피고소인의 행위",
        "공갈죄": "피고소인의 행위",
        "공갈 혐의": "피고소인의 행위",
        "공갈 행위": "피고소인의 행위",
        "강요죄": "피고소인의 행위",
        "강요 혐의": "피고소인의 행위",
        "강요 행위": "피고소인의 행위",
        "폭행죄": "피고소인의 행위",
        "폭행 혐의": "피고소인의 행위",
        "상해죄": "피고소인의 행위",
        "상해 혐의": "피고소인의 행위",
        "명예훼손죄": "피고소인의 행위",
        "명예훼손 혐의": "피고소인의 행위",
        "모욕죄": "피고소인의 행위",
        "모욕 혐의": "피고소인의 행위",
    }
    sanitized_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        compact_line = line.replace(" ", "")
        if (
            line.startswith("형법 제")
            or line.startswith("정보통신망법")
            or line.startswith("관련 법조")
            or line.startswith("관련사건")
            or line.startswith("첨부서류")
            or line.startswith("위 고소인")
            or line.endswith("귀중")
            or line.endswith("귀하")
            or line in {"미상", "-"}
            or compact_line.startswith("죄명:")
            or compact_line.startswith("혐의명:")
            or compact_line.startswith("적용법조:")
        ):
            continue
        cleaned = raw_line
        if allowed_charge:
            for pattern, replacement in charge_replacements.items():
                pattern_base = pattern.replace(" 혐의", "").replace(" 행위", "").removesuffix("죄")
                if pattern not in allowed_tokens and pattern_base not in allowed_tokens:
                    cleaned = cleaned.replace(pattern, replacement)
        else:
            cleaned = re.sub(r"(사기|폭행|상해|횡령|배임|업무방해|협박|공갈|강요|강도|명예훼손|모욕)\s*(등)?\s*혐의", "피고소인의 행위", cleaned)
            for pattern in _CHARGE_PATTERNS:
                cleaned = cleaned.replace(pattern, "피고소인의 행위")
        cleaned = cleaned.replace("피고소인을 피고소인의 행위로", "피고소인의 행위에 대하여")
        sanitized_lines.append(cleaned)
    return "\n".join(sanitized_lines).strip()

def _extract_openai_text(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("OpenAI 응답에 후보 문장이 없습니다.")

    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        finish_reason = choices[0].get("finish_reason", "unknown")
        raise ValueError(f"OpenAI 응답 텍스트가 비어 있습니다. finish_reason={finish_reason}")
    return text


async def generate_complaint(payload: ComplaintGenerateRequest) -> str:
    if not OPENAI_API_KEY:
        return _sanitize_complaint_text(_fallback_complaint(payload), payload.charge_name)

    request_body = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(payload)},
        ],
        "temperature": 0.2,
    }

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json=request_body,
        )
        response.raise_for_status()
        data = response.json()

    return _sanitize_complaint_text(_extract_openai_text(data), payload.charge_name)
