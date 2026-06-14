from pydantic import BaseModel, Field


class ComplaintGenerateRequest(BaseModel):
    complainant_name: str = Field(..., min_length=1, max_length=80)
    accused_name: str = Field(..., min_length=1, max_length=80)
    incident_date: str = Field("", max_length=120)
    incident_location: str = Field("", max_length=200)
    incident_description: str = Field(..., min_length=10, max_length=6000)
    evidence_summary: str = Field("", max_length=3000)
    requested_punishment: str = Field("", max_length=1000)
    charge_name: str = Field("", max_length=120)
    legal_references: list[str] = Field(default_factory=list, max_length=10)

    complainant_rrn: str = Field("", max_length=80)
    complainant_address: str = Field("", max_length=300)
    complainant_job: str = Field("", max_length=120)
    complainant_phone: str = Field("", max_length=80)

    accused_rrn: str = Field("", max_length=80)
    accused_address: str = Field("", max_length=300)
    accused_job: str = Field("", max_length=120)
    accused_phone: str = Field("", max_length=80)
    accused_identifier: str = Field("", max_length=200)

    police_station: str = Field("", max_length=160)
    filing_date: str = Field("", max_length=80)
    attachments: list[str] = Field(default_factory=list, max_length=20)


class ComplaintJobCreateResponse(BaseModel):
    complaint_id: int
    job_id: int
    status: str
    request_type: str
    usage_limit: int
    usage_used: int
    usage_remaining: int


class ComplaintJobStatusResponse(BaseModel):
    complaint_id: int
    job_id: int
    status: str
    complaint_text: str | None = None
    error_message: str | None = None


class ReferenceJobCreateResponse(BaseModel):
    complaint_id: int
    job_id: int
    status: str
    request_type: str
    usage_limit: int
    usage_used: int
    usage_remaining: int


class ReferenceJobStatusResponse(BaseModel):
    complaint_id: int
    job_id: int
    status: str
    result: dict | None = None
    error_message: str | None = None


class ComplaintPdfRequest(BaseModel):
    payload: ComplaintGenerateRequest
    complaint_text: str = Field(..., min_length=1)


class UsageTodayResponse(BaseModel):
    limit: int
    used: int
    remaining: int


class ReferenceSearchRequest(BaseModel):
    complainant_name: str = Field("", max_length=80)
    accused_name: str = Field("", max_length=80)
    incident_date: str = Field("", max_length=120)
    incident_location: str = Field("", max_length=200)
    incident_description: str = Field(..., min_length=10, max_length=6000)
    evidence_summary: str = Field("", max_length=3000)
    requested_punishment: str = Field("", max_length=1000)


class SimilarPrecedentItem(BaseModel):
    id: str
    title: str
    charge: str = ""
    source_url: str = ""
    issue: str = ""
    summary: str = ""
    fact: str = ""
    outcome: str = ""
    question: str = ""
    selection_reason: str = ""
    how_to_use_in_complaint: str = ""


class ReferenceGuidanceRequest(ReferenceSearchRequest):
    fact_summary: str = ""
    precedent: SimilarPrecedentItem


class ReferenceAnalyzeResponse(BaseModel):
    is_meaningful_case: bool = True
    invalid_reason: str = ""
    fact_summary: str = ""
    similar_precedent: SimilarPrecedentItem | None = None
    similar_precedents: list[SimilarPrecedentItem] = Field(default_factory=list)
    usage_limit: int
    usage_used: int
    usage_remaining: int
