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
DEFAULT_PURPOSE_TEXT = "저는 피고소인의 위 행위에 대하여 고소하오니 철저히 수사하여 법에 따라 처벌하여 주시기 바랍니다."

SYSTEM_PROMPT = (
    "당신은 대한민국 형사 고소장 초안 작성 보조자입니다. "
    "사실을 꾸미지 않고, 사용자가 입력한 내용만 근거로 고소인이 직접 제출하는 문서 형식의 한국어 초안을 작성합니다."
)

def _unknown(value: str, fallback: str = "미상") -> str:
    return value.strip() if value and value.strip() else fallback


def _legal_references_text(payload: ComplaintGenerateRequest) -> str:
    if not payload.legal_references:
        return "사용자 선택 참고자료 없음"
    return "\n".join(f"- {item}" for item in payload.legal_references[:10])


def _legal_reference_titles_text(payload: ComplaintGenerateRequest) -> str:
    titles = []
    for item in payload.legal_references[:10]:
        for line in str(item or "").splitlines():
            cleaned = line.strip()
            if cleaned.startswith("판례:"):
                titles.append(f"- {cleaned}")
                break
    return "\n".join(titles)


def _purpose_text(payload: ComplaintGenerateRequest) -> str:
    return DEFAULT_PURPOSE_TEXT


def _build_prompt(payload: ComplaintGenerateRequest) -> str:
    charge_instruction = f"- 3. 고소취지는 반드시 다음 문장으로만 작성하세요: {_purpose_text(payload)}"
    return f"""
아래 사용자의 진술과 보완 답변만 근거로 대한민국 형사 고소장 초안을 작성하세요.

출력 형식:
- 마크다운 기호(**, ###, ---)를 쓰지 마세요.
- 제목은 그대로 사용하세요: 고 소 장, 1. 고소인, 2. 피고소인, 3. 고소취지, 4. 범죄사실, 5. 고소이유, 6. 증거자료
- 제공되지 않은 사실은 만들지 말고, 모르는 개인정보는 '미상'으로 표시하세요.
- 죄명, 혐의명, 관련 법조를 새로 판단하지 말고, 죄명처럼 보이는 표현도 구체적 행위 사실 중심으로 풀어 쓰세요.
- 고소장은 제3자 보고서가 아니라 본인이 직접 제출하는 문서처럼 작성하세요.
- 본문에서는 가능한 한 '저는', '제가', '저에게', '피고소인은'을 사용하고, '고소인은', '피해자는' 같은 제3자 표현은 되도록 쓰지 마세요.
{charge_instruction}

작성 규칙:
- 4. 범죄사실에는 일시, 장소, 행위 방법, 피해 결과를 시간 순서대로 구체적으로 정리하세요.
- 5. 고소이유에는 범행 경위, 정황, 피해 내용, 고소하게 된 이유를 본인이 겪은 사실 중심으로 정리하세요.
- 법적 판단, 유죄 가능성, 판례 적용 여부를 단정하지 마세요.
- 마지막 알림 문구는 쓰지 마세요.

보완 답변 반영 규칙:
- 보완 질문/답변은 내용에 따라 4. 범죄사실 또는 5. 고소이유에 나누어 반영하세요.
- 침입·접근 방식, 협박·폭행 방법, 사용한 물건, 역할 분담, 피해 물품, 신고 경위처럼 사건 진행을 구체화하는 내용은 4. 범죄사실에 반영하세요.
- 범행 전후 정황, 피해가 계속되는 사정, 불안감·공포감, 고소하게 된 이유는 5. 고소이유에 반영하세요.
- 같은 사실을 4. 범죄사실과 5. 고소이유에 길게 반복하지 마세요.
- 선택 참고판례 정보는 초안 본문에 작성하지 말고, 참고판례의 죄명이나 사실관계를 현재 사건에 가져오지 마세요.

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

    4. 범죄사실
    발생 일시: {_unknown(payload.incident_date)}
    발생 장소: {_unknown(payload.incident_location)}
    {payload.incident_description}

    5. 고소이유
    저는 위 범죄사실과 같은 피고소인의 행위로 피해를 입었고, 이에 대해 수사를 통해 사실관계가 확인되기를 원합니다.
    {("※ 참고판례\n" + _legal_reference_titles_text(payload)) if payload.legal_references else ""}

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
    return _normalize_purpose_section("\n".join(sanitized_lines)).strip()


def _normalize_purpose_section(text: str) -> str:
    pattern = r"(?P<head>(?:^|\n)\s*3\.\s*고소취지\s*\n)(?P<body>.*?)(?=\n\s*4\.\s*범죄\s*사실|\n\s*4\.\s*범죄사실|\Z)"
    return re.sub(pattern, lambda match: f"{match.group('head')}{DEFAULT_PURPOSE_TEXT}\n", text, count=1, flags=re.S)

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
