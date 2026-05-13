import os
import re
import textwrap
import uuid
from pathlib import Path
from typing import Dict, Tuple

import httpx
from dotenv import load_dotenv

from schemas.complaint import ComplaintGenerateRequest

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

SYSTEM_PROMPT = (
    "당신은 대한민국 형사 고소장 초안 작성 보조자입니다. "
    "사실을 꾸미지 않고, 사용자가 입력한 내용만 근거로 제출 검토 가능한 문서 형식의 한국어 초안을 작성합니다."
)

_COMPLAINT_STORE: Dict[str, Tuple[ComplaintGenerateRequest, str]] = {}


def save_complaint(payload: ComplaintGenerateRequest, text: str) -> str:
    complaint_id = uuid.uuid4().hex
    _COMPLAINT_STORE[complaint_id] = (payload, text)
    return complaint_id


def get_complaint(complaint_id: str) -> Tuple[ComplaintGenerateRequest, str] | None:
    return _COMPLAINT_STORE.get(complaint_id)


def get_missing_fields(payload: ComplaintGenerateRequest) -> list[str]:
    checks = [
        ("고소인 주민등록번호", payload.complainant_rrn),
        ("고소인 주소", payload.complainant_address),
        ("고소인 휴대폰 번호", payload.complainant_phone),
        ("피고소인 휴대폰 번호 또는 기타사항", payload.accused_phone or payload.accused_identifier),
        ("제출 관서", payload.police_station),
        ("제출일", payload.filing_date),
    ]
    if not payload.evidence_summary and not payload.attachments:
        checks.append(("증거 자료", ""))
    return [label for label, value in checks if not str(value or "").strip()]


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
- 아래 번호와 제목을 그대로 사용하세요: 고 소 장, 1. 고소인, 2. 피고소인, 3. 고소취지, 4. 범죄사실, 5. 고소이유, 6. 증거자료, 7. 기타
- 사용자가 제공하지 않은 사실을 만들지 마세요.
- 모르는 개인정보는 '미상'으로만 표시하세요. '추후 보완 예정' 문구는 쓰지 마세요.
- 사건 날짜와 제출일을 혼동하지 마세요.
- 제출일이 비어 있으면 오늘 날짜를 임의로 쓰지 말고 '미상'이라고 쓰세요.
- AI가 죄명, 혐의명, 관련 법조를 새로 판단하거나 추가하지 마세요.
{charge_instruction}
- 4. 범죄사실에는 사용자가 입력한 사실만 정리하세요. 빠진 사실을 추측하거나 만들어 쓰지 마세요.
- 5. 고소이유에는 범죄사실을 뒷받침하는 경위, 정황, 고소 동기, 피해 내용을 정리하세요.
- 사용자가 선택한 판례/참고자료가 있으면 5. 고소이유 맨 아래에서 한 줄 띄운 뒤 '※ 참고판례'를 별도 줄 제목으로 쓰고, 그 아래에 선택한 참고자료 목록을 그대로 적으세요.
- '참고판례:'처럼 본문 문장 뒤에 붙여 쓰지 마세요.
- 선택한 참고자료를 넣을 때는 '유사한 사안에서 문제된 사례가 있으므로 본 건의 경위와 공개 범위 등을 면밀히 수사하여 주시기 바랍니다'처럼 조심스럽게 쓰세요.
- 판례가 곧바로 적용된다거나 유죄라고 단정하지 마세요.
- 7. 기타는 비워두세요. 참고판례를 7. 기타에 넣지 마세요.
- 판례의 적용 여부, 유죄 가능성, 범죄 성립 여부는 단정하지 마세요.
- 관련 법조, 형법 조문, 특정 죄명 섹션은 만들지 마세요.
- 관련사건의 수사 및 재판 여부 섹션은 작성하지 마세요. 해당 내용은 PDF 양식에서 사용자가 직접 체크합니다.
- 제출 관서, 제출일, 고소인 서명, 귀중/귀하 문구는 작성하지 마세요. 해당 내용은 PDF 양식에서 따로 처리합니다.
- 마지막 알림 문구는 쓰지 마세요. 서비스 화면에서 별도로 안내합니다.

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
사용자 선택 참고자료:
{_legal_references_text(payload)}
처벌 의사/요청 사항: {_unknown(payload.requested_punishment, '엄정한 수사와 처벌을 원함')}
제출 관서: {_unknown(payload.police_station)}
제출일: {_unknown(payload.filing_date)}
첨부서류:
{_attachments_text(payload)}
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

    7. 기타


    첨부서류
    {_attachments_text(payload)}
    """).strip()


_CHARGE_PATTERNS = [
    "사기죄", "사기 혐의", "폭행죄", "폭행 혐의", "상해죄", "상해 혐의", "횡령죄", "횡령 혐의",
    "강도죄", "강도 혐의", "명예훼손죄", "명예훼손 혐의", "모욕죄", "모욕 혐의",
]


def _sanitize_complaint_text(text: str, allowed_charge: str = "") -> str:
    allowed_charge = (allowed_charge or "").strip()
    sanitized_lines = []
    skip_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        compact_line = line.replace(" ", "")
        if line.startswith("7.") and ("관련사건" in line or "관련 법조" in line or "관련법조" in line or "제출 관서" in line):
            skip_section = True
            continue
        if skip_section:
            if line.startswith("8."):
                raw_line = re.sub(r"^\s*8\.", "7.", raw_line, count=1)
                line = raw_line.strip()
                compact_line = line.replace(" ", "")
                skip_section = False
            elif line.startswith("첨부서류"):
                raw_line = "7. 기타"
                line = raw_line
                compact_line = line.replace(" ", "")
                skip_section = False
            else:
                continue
        elif line.startswith("8."):
            raw_line = re.sub(r"^\s*8\.", "7.", raw_line, count=1)
            line = raw_line.strip()
            compact_line = line.replace(" ", "")
        if (
            line.startswith("형법 제")
            or line.startswith("정보통신망법")
            or line.startswith("관련 법조")
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
        if not allowed_charge:
            cleaned = re.sub(r"(사기|폭행|상해|횡령|강도|명예훼손|모욕)\s*(등)?\s*혐의", "피고소인의 행위", cleaned)
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


async def generate_complaint(payload: ComplaintGenerateRequest) -> tuple[str, bool]:
    if not OPENAI_API_KEY:
        return _sanitize_complaint_text(_fallback_complaint(payload), payload.charge_name), True

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

    return _sanitize_complaint_text(_extract_openai_text(data), payload.charge_name), False


