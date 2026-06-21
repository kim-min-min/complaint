import re
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from schemas.complaint import ComplaintGenerateRequest

FONT_PATH = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def _register_fonts() -> tuple[str, str]:
    regular = "MalgunGothic"
    bold = "MalgunGothicBold"
    if FONT_PATH.exists() and regular not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(regular, str(FONT_PATH)))
    if FONT_BOLD_PATH.exists() and bold not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(bold, str(FONT_BOLD_PATH)))
    if FONT_PATH.exists():
        return (regular, bold if FONT_BOLD_PATH.exists() else regular)

    cid_font = "HYGothic-Medium"
    if cid_font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(cid_font))
    return cid_font, cid_font


def _clean(value: str | None, fallback: str = "") -> str:
    value = (value or "").strip()
    return value if value else fallback


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph("<br/>".join(escape(line) for line in str(text).splitlines()), style)


def _section(text: str, body_style: ParagraphStyle, space_before: int = 8) -> list:
    return [Spacer(1, space_before * mm), _p(text, body_style), Spacer(1, 3 * mm)]


def _extract_section(complaint_text: str, number: int, fallback: str = "") -> str:
    pattern = rf"(?:^|\n)\s*{number}\.\s*[^\n]*\n(?P<body>.*?)(?=\n\s*{number + 1}\.\s|\Z)"
    match = re.search(pattern, complaint_text, flags=re.S)
    if not match:
        return fallback
    body = match.group("body").strip()
    return body or fallback


def _date_line(date_text: str) -> str:
    return _clean(date_text, "20          년          월          일")


def _blank_line(width_mm: int) -> str:
    return "_" * width_mm


def _legal_references_text(payload: ComplaintGenerateRequest) -> str:
    if not payload.legal_references:
        return ""
    items = "\n".join(f"- {_reference_title(item)}" for item in payload.legal_references[:10] if _reference_title(item))
    return f"※ 참고판례\n{items}"


def _reference_title(value: str) -> str:
    for line in str(value or "").splitlines():
        cleaned = line.strip()
        if cleaned.startswith("판례:"):
            return cleaned
    return ""


def _normalize_reference_heading(text: str) -> str:
    normalized = re.sub(r"\s*※?\s*참고판례\s*[:：]\s*", "\n\n※ 참고판례\n", str(text or ""))
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


def _visual_line_count(text: str, chars_per_line: int = 43) -> int:
    lines = str(text or "").splitlines() or [""]
    count = 0
    for line in lines:
        length = len(line.strip())
        count += max(1, (length + chars_per_line - 1) // chars_per_line)
    return count


def _needs_appendix(text: str, max_chars: int = 780, max_lines: int = 12) -> bool:
    cleaned = _clean(text)
    return len(cleaned) > max_chars or _visual_line_count(cleaned) > max_lines


def _reason_with_references(reason: str, payload: ComplaintGenerateRequest) -> str:
    reason = _normalize_reference_heading(reason)
    references = _legal_references_text(payload)
    if not references or "참고판례" in reason:
        return reason
    return f"{reason.rstrip()}\n\n{references}"


def _default_purpose() -> str:
    return "저는 피고소인의 위 행위에 대하여 고소하오니 철저히 수사하여 법에 따라 처벌하여 주시기 바랍니다."


def _paragraph_block(text: str, style: ParagraphStyle, min_height_mm: int = 80) -> Table:
    content = _p(_clean(text, " "), style)
    table = Table([[content]], colWidths=[170 * mm], rowHeights=[min_height_mm * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table



def _phone_group_table(phone: str, styles: dict) -> Table:
    phone_text = f"(휴대폰) {_clean(phone)}" if _clean(phone) else "(휴대폰)"
    table = Table(
        [[
            _p(phone_text, styles["cell_phone_left"]),
            _p("(자택)", styles["cell_phone_left"]),
            _p("(사무실)", styles["cell_phone_left"]),
        ]],
        colWidths=[52 * mm, 46 * mm, 47 * mm],
        rowHeights=[11 * mm],
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table
def _person_table(payload: ComplaintGenerateRequest, role: str, styles: dict) -> Table:
    is_complainant = role == "complainant"
    if is_complainant:
        name = payload.complainant_name
        rrn = payload.complainant_rrn
        address = payload.complainant_address
        job = payload.complainant_job
        phone = payload.complainant_phone
        extra = ""
    else:
        name = payload.accused_name
        rrn = payload.accused_rrn
        address = payload.accused_address
        job = payload.accused_job
        phone = payload.accused_phone
        extra = payload.accused_identifier

    data = [
        [_p("성    명", styles["cell_center"]), _p(_clean(name), styles["cell"]), _p("주민등록번호", styles["cell_center"]), _p(_clean(rrn, "-"), styles["cell_center"])],
        [_p("주    소", styles["cell_center"]), _p(_clean(address), styles["cell"]), "", ""],
        [_p("직    업", styles["cell_center"]), _p(_clean(job), styles["cell"]), _p("사무실\n주소", styles["cell_center"]), _p("", styles["cell"])],
        [_p("전    화", styles["cell_center"]), _phone_group_table(phone, styles), "", ""],
        [_p("이메일", styles["cell_center"]), _p("", styles["cell"]), "", ""],
    ]

    if is_complainant:
        data.append([_p("대리인에\n의한 고소", styles["cell_center"]), _p("□ 법정대리인  (성명:                 / 연락처:                 )\n□ 고소대리인  (성명: 변호사            / 연락처:                 )", styles["cell"]), "", ""])
    else:
        data.append([_p("기타사항", styles["cell_center"]), _p(_clean(extra), styles["cell"]), "", ""])

    table = Table(data, colWidths=[25 * mm, 56 * mm, 32 * mm, 57 * mm], rowHeights=[13 * mm, 13 * mm, 13 * mm, 13 * mm, 13 * mm, 18 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (1, 1), (3, 1)),
        ("SPAN", (1, 3), (3, 3)),
        ("SPAN", (1, 4), (3, 4)),
        ("SPAN", (1, 5), (3, 5)),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _related_case_table(styles: dict) -> Table:
    data = [
        [_p("① 중복 고소 여부", styles["cell_center"]), _p("본 고소장과 같은 내용의 고소장을 다른 검찰청 또는 경찰서에 제출하거나 제출하였던 사실이 있습니다 □ / 없습니다 □", styles["cell"])],
        [_p("② 관련 형사사건\n수사 유무", styles["cell_center"]), _p("본 고소장에 기재된 범죄사실과 관련된 사건 또는 공범에 대하여 검찰청이나 경찰서에서 수사 중에 있습니다 □ / 수사 중에 있지 않습니다 □", styles["cell"])],
        [_p("③ 관련 민사소송\n유무", styles["cell_center"]), _p("본 고소장에 기재된 범죄사실과 관련된 사건에 대하여 법원에서 민사소송 중에 있습니다 □ / 민사소송 중에 있지 않습니다 □", styles["cell"])],
    ]
    table = Table(data, colWidths=[42 * mm, 128 * mm], rowHeights=[18 * mm, 22 * mm, 22 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _build_styles(font_name: str, bold_font: str) -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName=bold_font, fontSize=23, leading=30, alignment=TA_CENTER, spaceAfter=4 * mm),
        "subtitle": ParagraphStyle("subtitle", parent=base["BodyText"], fontName=font_name, fontSize=8.5, leading=12, alignment=TA_CENTER),
        "heading": ParagraphStyle("heading", parent=base["Heading2"], fontName=bold_font, fontSize=15, leading=20, alignment=TA_LEFT),
        "annex_title": ParagraphStyle("annex_title", parent=base["Heading1"], fontName=bold_font, fontSize=15, leading=20, alignment=TA_LEFT),
        "annex_heading": ParagraphStyle("annex_heading", parent=base["Heading2"], fontName=bold_font, fontSize=14, leading=18, alignment=TA_LEFT),
        "annex_note": ParagraphStyle("annex_note", parent=base["BodyText"], fontName=font_name, fontSize=9.5, leading=15, alignment=TA_CENTER),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=font_name, fontSize=10.5, leading=17, alignment=TA_LEFT),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName=font_name, fontSize=8.2, leading=11.2, alignment=TA_LEFT),
        "cell": ParagraphStyle("cell", parent=base["BodyText"], fontName=font_name, fontSize=9.5, leading=13, alignment=TA_LEFT),
        "cell_center": ParagraphStyle("cell_center", parent=base["BodyText"], fontName=font_name, fontSize=9.5, leading=13, alignment=TA_CENTER),
        "cell_phone": ParagraphStyle("cell_phone", parent=base["BodyText"], fontName=font_name, fontSize=8.8, leading=11, alignment=TA_CENTER),
        "cell_phone_left": ParagraphStyle("cell_phone_left", parent=base["BodyText"], fontName=font_name, fontSize=8.8, leading=11, alignment=TA_LEFT),
        "small_center": ParagraphStyle("small_center", parent=base["BodyText"], fontName=font_name, fontSize=8.2, leading=11.2, alignment=TA_CENTER),
        "body_center": ParagraphStyle("body_center", parent=base["BodyText"], fontName=font_name, fontSize=10.5, leading=17, alignment=TA_CENTER),
        "center": ParagraphStyle("center", parent=base["BodyText"], fontName=font_name, fontSize=11, leading=18, alignment=TA_CENTER),
        "center_bold": ParagraphStyle("center_bold", parent=base["BodyText"], fontName=bold_font, fontSize=13, leading=20, alignment=TA_CENTER),
    }



def _annex_person_table(styles: dict) -> Table:
    data = [
        [_p("성    명", styles["cell_center"]), _p("", styles["cell"]), _p("주민등록번호", styles["cell_center"]), _p("-", styles["cell_center"]), ""],
        [_p("주    소", styles["cell_center"]), _p("자택 :\n직장 :", styles["cell"]), "", _p("직업", styles["cell_center"]), _p("", styles["cell"])],
        [_p("전    화", styles["cell_center"]), _phone_group_table("", styles), "", "", ""],
        [_p("입증하려는\n내용", styles["cell_center"]), _p("", styles["cell"]), "", "", ""],
    ]
    table = Table(data, colWidths=[28 * mm, 43 * mm, 30 * mm, 25 * mm, 44 * mm], rowHeights=[13 * mm, 18 * mm, 13 * mm, 26 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (3, 0), (4, 0)),
        ("SPAN", (1, 1), (2, 1)),
        ("SPAN", (1, 2), (4, 2)),
        ("SPAN", (1, 3), (4, 3)),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _annex_document_table(styles: dict, evidence_names: list[str]) -> Table:
    data = [[_p("순번", styles["cell_center"]), _p("증거", styles["cell_center"]), _p("작성자", styles["cell_center"]), _p("제출 유무", styles["cell_center"])]]
    rows = evidence_names[:10]
    rows.extend([""] * max(0, 5 - len(rows)))
    for idx, name in enumerate(rows, start=1):
        data.append([
            _p(str(idx), styles["cell_center"]),
            _p(name, styles["cell"]),
            _p("고소인" if name else "", styles["cell_center"]),
            _p("■ 접수시 제출  □ 수사 중 제출" if name else "□ 접수시 제출  □ 수사 중 제출", styles["cell_center"]),
        ])
    table = Table(data, colWidths=[13 * mm, 57 * mm, 30 * mm, 70 * mm], rowHeights=[13 * mm] + [14 * mm] * len(rows))
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return table


def _annex_object_table(styles: dict) -> Table:
    data = [[_p("순번", styles["cell_center"]), _p("증거", styles["cell_center"]), _p("소유자", styles["cell_center"]), _p("제출 유무", styles["cell_center"])]]
    for idx in range(1, 6):
        data.append([_p(str(idx), styles["cell_center"]), _p("", styles["cell"]), _p("", styles["cell"]), _p("□ 접수시 제출  □ 수사 중 제출", styles["cell_center"])])
    table = Table(data, colWidths=[13 * mm, 57 * mm, 30 * mm, 70 * mm], rowHeights=[13 * mm] + [14 * mm] * 5)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.8, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    return table


def _append_evidence_annex(story: list, styles: dict, payload: ComplaintGenerateRequest) -> None:
    evidence_names = _evidence_names(payload)
    story.append(PageBreak())
    story.append(Spacer(1, 4 * mm))
    story.append(_p("별지 : 증거자료 세부 목록", styles["annex_title"]))
    story.append(_p("(범죄사실 입증을 위해 제출하려는 증거에 대하여 아래 각 증거별로 해당 난을 구체적으로 작성해 주시기 바랍니다)", styles["annex_note"]))
    story.append(Spacer(1, 14 * mm))
    story.append(_p("1. 인적증거 (목격자, 기타 참고인 등)", styles["annex_heading"]))
    story.append(Spacer(1, 7 * mm))
    story.append(_annex_person_table(styles))
    story.append(Spacer(1, 5 * mm))
    story.append(_p("※ 참고인의 인적사항과 연락처를 정확히 알 수 없으면 참고인을 특정할 수 있도록 성별, 외모 등을 '입증하려는 내용'란에 아는 대로 기재하시기 바랍니다.", styles["small"]))
    story.append(Spacer(1, 9 * mm))
    story.append(_p("2. 증거서류 (진술서, 차용증, 각서, 금융거래내역서, 진단서 등)", styles["annex_heading"]))
    story.append(Spacer(1, 6 * mm))
    story.append(_annex_document_table(styles, evidence_names))
    story.append(Spacer(1, 5 * mm))
    story.append(_p("※ 증거란에 각 증거서류를 개별적으로 기재하고, 제출 유무란에는 고소장 접수시 제출하는지 또는 수사 중 제출할 예정인지 표시하시기 바랍니다.", styles["small"]))
    story.append(PageBreak())
    story.append(Spacer(1, 12 * mm))
    story.append(_p("3. 증거물", styles["annex_heading"]))
    story.append(Spacer(1, 8 * mm))
    story.append(_annex_object_table(styles))
    story.append(Spacer(1, 6 * mm))
    story.append(_p("※ 증거란에 각 증거물을 개별적으로 기재하고, 소유자란에는 고소장 제출시 누가 소유하고 있는지, 제출 유무란에는 고소장 접수시 제출하는지 또는 수사 중 제출할 예정인지 표시하시기 바랍니다.", styles["small"]))
    story.append(Spacer(1, 15 * mm))
    story.append(_p("4. 기타 증거", styles["annex_heading"]))


def _append_text_appendix(story: list, styles: dict, title: str, text: str) -> None:
    story.append(PageBreak())
    story.append(Spacer(1, 4 * mm))
    story.append(_p(title, styles["annex_title"]))
    story.append(Spacer(1, 8 * mm))
    story.append(_p(_clean(text, " "), styles["body"]))


def _evidence_names(payload: ComplaintGenerateRequest) -> list[str]:
    names = []
    for value in payload.attachments:
        cleaned = _clean(value)
        if cleaned:
            names.append(cleaned)
    for attachment in payload.evidence_attachments:
        cleaned = _clean(attachment.name)
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def _evidence_list_text(payload: ComplaintGenerateRequest) -> str:
    return "\n".join(f"{index}. {name}" for index, name in enumerate(_evidence_names(payload), start=1))


def _image_flowable(data_base64: str, max_width: float, max_height: float):
    if not data_base64:
        return None
    try:
        import base64
        from reportlab.platypus import Image

        raw = base64.b64decode(data_base64, validate=True)
        image = Image(BytesIO(raw))
        scale = min(max_width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        return image
    except Exception:
        return None


def _append_evidence_images(story: list, styles: dict, payload: ComplaintGenerateRequest) -> None:
    max_width = 170 * mm
    max_height = 220 * mm
    for index, attachment in enumerate(payload.evidence_attachments, start=1):
        image = _image_flowable(attachment.data_base64, max_width, max_height)
        if image is None:
            continue
        story.append(PageBreak())
        story.append(Spacer(1, 4 * mm))
        story.append(_p(f"증거 {index}. {_clean(attachment.name, attachment.filename or '증거자료')}", styles["annex_title"]))
        if _clean(attachment.filename):
            story.append(_p(f"파일명: {attachment.filename}", styles["small"]))
        story.append(Spacer(1, 8 * mm))
        story.append(image)


def build_complaint_pdf(payload: ComplaintGenerateRequest, complaint_text: str) -> bytes:
    buffer = BytesIO()
    font_name, bold_font = _register_fonts()
    styles = _build_styles(font_name, bold_font)

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        title="고소장",
    )

    facts = _extract_section(complaint_text, 4, payload.incident_description)
    reason = _reason_with_references(
        _extract_section(complaint_text, 5, "피고소인의 행위 경위와 정황, 고소를 하게 된 동기와 사유는 범죄사실 기재 내용과 같습니다."),
        payload,
    )
    evidence = _evidence_list_text(payload)
    station = _clean(payload.police_station, _blank_line(18))
    purpose = _extract_section(complaint_text, 3, _default_purpose())
    facts_needs_appendix = _needs_appendix(facts, max_chars=900, max_lines=13)
    reason_needs_appendix = _needs_appendix(reason, max_chars=780, max_lines=12)
    facts_main = "별지 범죄사실 기재와 같습니다." if facts_needs_appendix else facts
    reason_main = "별지 고소이유 기재와 같습니다." if reason_needs_appendix else reason

    story = []
    story.append(_p("고    소    장", styles["title"]))
    story.append(_p("(고소장 기재사항 중 * 표시된 항목은 반드시 기재하여야 합니다.)", styles["subtitle"]))
    story.extend(_section("1. 고소인*", styles["heading"], 6))
    story.append(_person_table(payload, "complainant", styles))
    story.append(Spacer(1, 3 * mm))
    story.append(_p("※ 고소인이 법인 또는 단체인 경우에는 상호 또는 단체명, 대표자, 법인등록번호, 주된 사무소의 소재지, 전화 등 연락처를 기재하여야 합니다.", styles["small"]))
    story.append(_p("※ 미성년자의 친권자 등 법정대리인이나 변호사에 의한 고소대리의 경우 이를 증명할 수 있는 서류를 첨부하시기 바랍니다.", styles["small"]))
    story.extend(_section("2. 피고소인*", styles["heading"], 5))
    story.append(_person_table(payload, "accused", styles))
    story.append(Spacer(1, 2 * mm))
    story.append(_p("※ 기타사항에는 고소인과의 관계 및 피고소인의 인적사항과 연락처를 정확히 알 수 없을 경우 성별, 특징적 외모, 인상착의 등을 구체적으로 기재하시기 바랍니다.", styles["small"]))

    story.append(PageBreak())
    story.extend(_section("3. 고소취지*", styles["heading"], 0))
    story.append(_p("(죄명 및 피고소인에 대한 처벌의사 기재)", styles["subtitle"]))
    story.append(_p(purpose, styles["body"]))
    story.extend(_section("4. 범죄사실*", styles["heading"], 10))
    story.append(_paragraph_block(facts_main, styles["body"], 88))
    story.append(_p("※ 범죄사실은 형법 등 처벌법규에 해당하는 사실에 대하여 일시, 장소, 범행방법, 결과 등을 구체적으로 특정하여 기재하여야 합니다.", styles["small"]))
    story.extend(_section("5. 고소이유", styles["heading"], 8))
    story.append(_paragraph_block(reason_main, styles["body"], 72))
    story.append(_p("※ 고소이유에는 피고소인의 범행 경위 및 정황, 고소를 하게 된 동기와 사유 등 범죄사실을 뒷받침하는 내용을 간략, 명료하게 기재하여야 합니다.", styles["small"]))

    story.append(PageBreak())
    story.extend(_section("6. 증거자료", styles["heading"], 0))
    story.append(_p("(■ 해당란에 체크하여 주시기 바랍니다)", styles["subtitle"]))
    has_evidence = bool(evidence.strip() or payload.evidence_attachments)
    story.append(_p(("□ 고소인은 고소인의 진술 외에 제출할 증거가 없습니다.\n■ 고소인은 고소인의 진술 외에 제출할 증거가 있습니다." if has_evidence else "■ 고소인은 고소인의 진술 외에 제출할 증거가 없습니다.\n□ 고소인은 고소인의 진술 외에 제출할 증거가 있습니다."), styles["body"]))
    if has_evidence:
        story.append(_p(f"☞ 제출할 증거의 세부내역은 별지를 작성하여 첨부합니다.\n{evidence}", styles["body"]))
    story.extend(_section("7. 관련사건의 수사 및 재판 여부*", styles["heading"], 8))
    story.append(_p("(■ 해당란에 체크하여 주시기 바랍니다)", styles["subtitle"]))
    story.append(_related_case_table(styles))
    story.extend(_section("기타사항", styles["heading"], 8))
    story.append(_paragraph_block("", styles["body"], 25))
    story.append(_p("※ ①, ②항은 반드시 표시하여야 하며, 만일 본 고소내용과 동일한 사건 또는 관련 형사사건이 수사·재판 중이라면 어느 검찰청, 경찰서에서 수사 중인지, 어느 법원에서 재판 중인지 아는 범위에서 기타사항란에 기재하여야 합니다.", styles["small"]))
    story.extend(_section("8. 기타", styles["heading"], 8))
    story.append(_paragraph_block("", styles["body"], 26))

    story.append(PageBreak())
    story.append(Spacer(1, 18 * mm))
    story.append(_p("(고소내용에 대한 진실확약)", styles["subtitle"]))
    story.append(_p("본 고소장에 기재한 내용은 고소인이 알고 있는 지식과 경험을 바탕으로 모두 사실대로 작성하였으며, 만일 허위사실을 고소하였을 때에는 형법 제156조 무고죄로 처벌받을 것임을 서약합니다.", styles["body_center"]))
    story.append(Spacer(1, 24 * mm))
    story.append(_p(_date_line(payload.filing_date), styles["center"]))
    story.append(Spacer(1, 6 * mm))
    story.append(_p(f"고소인    {_clean(payload.complainant_name)}        (인)*", styles["center"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_p("제출인                      (인)", styles["center"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_p("※ 고소장 제출일을 기재하여야 하며, 고소인 난에는 고소인이 직접 자필로 서명 날(무)인 해야 합니다.", styles["small_center"]))
    story.append(Spacer(1, 12 * mm))
    story.append(_p(f"{station} 귀중", styles["center_bold"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_p("※ 고소장은 가까운 경찰서에 제출하셔도 됩니다.", styles["small_center"]))

    if facts_needs_appendix:
        _append_text_appendix(story, styles, "별지 : 범죄사실", facts)
    if reason_needs_appendix:
        _append_text_appendix(story, styles, "별지 : 고소이유", reason)

    _append_evidence_annex(story, styles, payload)
    if has_evidence:
        _append_evidence_images(story, styles, payload)

    doc.build(story)
    return buffer.getvalue()




