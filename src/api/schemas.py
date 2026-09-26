"""Request/response models for the HTTP API (these drive the generated TypeScript client)."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from database.models import (
    ComplaintStatus,
    IngestStatus,
    ReviewAction,
    Role,
    RuleType,
    RunStatus,
    VersionStatus,
)
from schemas.complaint_analysis import ComplaintAnalysis


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str
    issues: list[str] = Field(default_factory=list)


# --- users -------------------------------------------------------------------


class DepartmentRef(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class UserOut(ORMModel):
    id: uuid.UUID
    email: str | None
    full_name: str | None
    role: Role
    is_active: bool
    department: DepartmentRef | None


class UserUpdate(BaseModel):
    role: Role | None = None
    department_id: uuid.UUID | None = None
    is_active: bool | None = None


# --- taxonomy ----------------------------------------------------------------


class DepartmentOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class DepartmentCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    is_active: bool | None = None


class SubcategoryOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool


class CategoryOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    subcategories: list[SubcategoryOut]


class CategoryCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class CategoryUpdate(DepartmentUpdate):
    pass


class SubcategoryCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,59}$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class SlaPolicyOut(ORMModel):
    id: uuid.UUID
    priority: str
    name: str
    first_response_minutes: int
    resolution_minutes: int
    at_risk_threshold_pct: int


class SlaPolicyUpdate(BaseModel):
    first_response_minutes: int | None = Field(default=None, gt=0)
    resolution_minutes: int | None = Field(default=None, gt=0)
    at_risk_threshold_pct: int | None = Field(default=None, ge=1, le=99)


# --- knowledge base ----------------------------------------------------------


class DocumentTypeOut(BaseModel):
    code: str
    name: str
    precedence: int


class DocumentVersionOut(ORMModel):
    id: uuid.UUID
    version: str
    status: VersionStatus
    effective_date: date
    expiry_date: date | None
    file_name: str
    media_type: str
    size_bytes: int
    ingest_status: IngestStatus
    ingest_error: str | None
    page_count: int | None
    chunk_count: int
    created_at: datetime
    processed_at: datetime | None


class DocumentOut(ORMModel):
    id: uuid.UUID
    doc_code: str
    title: str
    doc_type: str
    versions: list[DocumentVersionOut]


class ChunkOut(ORMModel):
    chunk_code: str
    ordinal: int
    section: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    content: str
    token_count: int


class SearchResultOut(BaseModel):
    chunk_code: str
    doc_code: str
    doc_title: str
    doc_type: str
    precedence: int
    version: str
    section: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    content: str
    score: float


# --- complaints ----------------------------------------------------------------


class ComplaintCreate(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(max_length=6000)
    product_service: str | None = Field(default=None, max_length=200)
    order_ref: str | None = Field(default=None, max_length=20)
    previous_complaint_ref: str | None = Field(default=None, max_length=20)
    channel: str = "web_form"
    preferred_contact_channel: str | None = None
    requested_resolution: str | None = Field(default=None, max_length=1000)
    customer_ref: str | None = Field(
        default=None, description="Staff only: submit on behalf of this customer"
    )


class ComplaintEventOut(ORMModel):
    event_type: str
    from_status: str | None
    to_status: str | None
    message: str
    created_at: datetime


class OrderOut(ORMModel):
    order_ref: str
    product_name: str
    product_category: str
    amount: float
    shipping_method: str
    order_date: date
    committed_delivery_date: date
    delivered_date: date | None
    status: str


class ComplaintSummary(BaseModel):
    """List row. Classification fields are empty for customers."""

    complaint_ref: str
    title: str
    status: ComplaintStatus
    created_at: datetime
    updated_at: datetime
    customer_ref: str
    customer_name: str
    department_code: str | None
    category_code: str | None = None
    priority: str | None = None
    urgency: str | None = None
    sentiment: str | None = None
    escalation_level: int | None = None
    needs_review: bool = False
    verification: str | None = None


class ComplaintPage(BaseModel):
    items: list[ComplaintSummary]
    total: int


class ComplaintDetail(ComplaintSummary):
    description: str
    product_service: str | None
    order: OrderOut | None
    channel: str
    preferred_contact_channel: str | None
    requested_resolution: str | None
    previous_complaint_ref: str | None
    events: list[ComplaintEventOut]
    # staff-only details (None for customers)
    customer_type: str | None = None
    subcategory_code: str | None = None
    signals: dict[str, list[str]] | None = None
    entities: dict[str, Any] | None = None
    intake_warnings: list[str] | None = None
    review_reason: str | None = None
    supporting_departments: list[str] | None = None
    duplicate_of_ref: str | None = None
    related_complaint_ref: str | None = None
    similarity: float | None = None
    approved_response: str | None = None


class AnalysisRunSummary(ORMModel):
    id: uuid.UUID
    status: RunStatus
    created_at: datetime
    completed_at: datetime | None
    provider: str | None
    model: str | None
    prompt_name: str | None
    prompt_version: str | None
    schema_version: str | None
    attempts: int
    latency_ms: int
    input_tokens: int
    output_tokens: int


class AnalysisRunOut(AnalysisRunSummary):
    retrieved_policies: list[dict[str, Any]]
    output: ComplaintAnalysis | None
    validation_errors: list[str]
    error: str | None


class ComplaintAnalysisOut(BaseModel):
    latest: AnalysisRunOut | None
    history: list[AnalysisRunSummary]


# --- rule matrix ---------------------------------------------------------------


class RuleOut(ORMModel):
    rule_id: str
    rule_type: RuleType
    description: str
    category: str | None
    subcategory: str | None
    condition: str
    department: str | None
    supporting_departments: list[str]
    urgency: str | None
    priority: str | None
    escalation_level: int
    required_actions: list[str]
    prohibited_actions: list[str]
    policy_refs: list[str]
    follow_up_type: str | None
    follow_up_hours: int | None
    rule_priority: int
    is_active: bool
    version: int


class RuleWrite(BaseModel):
    """Create or replace a rule (all fields validated like the CSV import)."""

    rule_id: str
    rule_type: RuleType
    description: str = Field(min_length=3)
    category: str | None = None
    subcategory: str | None = None
    condition: str = ""
    department: str | None = None
    supporting_departments: list[str] = []
    urgency: str | None = None
    priority: str | None = None
    escalation_level: int = 0
    required_actions: list[str] = []
    prohibited_actions: list[str] = []
    policy_refs: list[str] = []
    follow_up_type: str | None = None
    follow_up_hours: int | None = None
    rule_priority: int = 50
    is_active: bool = True


class FactOut(BaseModel):
    name: str
    type: str
    description: str


# --- validation and review -------------------------------------------------------


class CheckResultOut(BaseModel):
    code: str
    name: str
    status: str
    severity: str
    message: str
    expected: Any = None
    actual: Any = None
    evidence: list[str] = []
    correctable: bool = False


class ComparisonRowOut(BaseModel):
    field: str
    genai: Any
    python: Any
    match: bool
    explanation: str
    expected: Any = None


class ValidationRunOut(ORMModel):
    id: uuid.UUID
    analysis_run_id: uuid.UUID | None
    verdict: str
    score: float
    checks: list[CheckResultOut]
    python_decision: dict[str, Any]
    comparison: list[ComparisonRowOut]
    final_recommendation: dict[str, Any]
    corrections: list[str]
    review_reasons: list[str]
    rules_version: str
    created_at: datetime


class ReviewTaskOut(BaseModel):
    id: uuid.UUID
    status: str
    reasons: list[str]
    priority: str | None
    created_at: datetime
    resolved_at: datetime | None
    complaint: ComplaintSummary


class ReviewActionIn(BaseModel):
    action: ReviewAction
    comment: str | None = Field(default=None, max_length=2000)
    response_body: str | None = Field(default=None, max_length=5000)
    category: str | None = None
    subcategory: str | None = None
    department: str | None = None
    escalation_level: int | None = None


class ReviewerDecisionOut(ORMModel):
    id: int
    action: ReviewAction
    comment: str | None
    before: dict[str, Any]
    after: dict[str, Any]
    created_at: datetime
    reviewer_id: uuid.UUID


class StatusChangeIn(BaseModel):
    status: ComplaintStatus
    note: str | None = Field(default=None, max_length=500)
