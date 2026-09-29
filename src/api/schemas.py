"""Request/response models for the HTTP API (these drive the generated TypeScript client)."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app_settings.model import (
    AiSettings,
    BrandingText,
    EmailSettings,
    OperationsSettings,
    OrderSettings,
    RuntimeSettings,
)
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
    warnings: list[str] = []
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
    # Customer-facing progress (SRS Step 61) and SLA tracking (Steps 55-56, staff only).
    resolved_at: datetime | None = None
    latest_update: str | None = None
    latest_update_at: datetime | None = None
    sla_status: str | None = None
    first_response_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    first_responded_at: datetime | None = None


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


# --- dashboards, analytics and reports -----------------------------------------------


class DistributionItem(BaseModel):
    key: str
    label: str
    count: int
    pct: float | None


class OverviewOut(BaseModel):
    total: int
    open: int
    resolved: int
    escalated: int
    open_escalated: int
    unclassified: int
    needs_review: int
    sla_at_risk: int
    sla_breached: int
    sla_met: int
    sla_missed: int
    repeat: int
    verified: int
    corrected: int
    flagged: int
    avg_resolution_hours: float | None
    sla_compliance_pct: float | None
    analysed: int
    mismatches: int
    open_reviews: int


class VolumePoint(BaseModel):
    period: str
    total: int
    escalated: int
    repeat: int
    resolved: int


class ResolutionTimeRow(BaseModel):
    priority: str
    resolved: int
    avg_hours: float | None
    median_hours: float | None
    within_sla_pct: float | None


class DepartmentRow(BaseModel):
    department: str
    label: str
    total: int
    open: int
    resolved: int
    escalated: int
    in_review: int
    at_risk: int
    breached: int
    repeat: int
    avg_resolution_hours: float | None
    sla_compliance_pct: float | None


class ComplaintRow(BaseModel):
    complaint_ref: str
    customer_ref: str
    created_at: datetime
    title: str
    category_code: str | None
    subcategory_code: str | None
    department_code: str | None
    priority: str | None
    urgency: str | None
    sentiment: str | None
    escalation_level: int | None
    status: str
    verification: str | None
    sla_status: str
    resolution_due_at: datetime | None
    resolved_at: datetime | None
    product: str
    needs_review: bool


class TrendOut(BaseModel):
    kind: str
    key: str
    label: str
    current: int
    previous: int
    change_pct: float | None
    message: str


class AgreementOut(BaseModel):
    compared: int
    mismatched: int
    verdicts: dict[str, int]
    agreement_pct: dict[str, float | None]


class ReasonCount(BaseModel):
    reason: str
    count: int


class ReviewStatsOut(BaseModel):
    open: int
    resolved: int
    avg_hours_to_resolve: float | None
    decisions: dict[str, int]
    top_reasons: list[ReasonCount]


class PolicyUsageRow(BaseModel):
    doc_code: str
    versions: str
    retrieved: int
    cited: int
    required_by_rules: int


class AdminDashboardOut(BaseModel):
    overview: OverviewOut
    distributions: dict[str, list[DistributionItem]]
    departments: list[DepartmentRow]
    sla_risks: list[ComplaintRow]
    trends: list[TrendOut]
    agreement: AgreementOut
    reviews: ReviewStatsOut


class AnalyticsOut(BaseModel):
    overview: OverviewOut
    volume: list[VolumePoint]
    distributions: dict[str, list[DistributionItem]]
    resolution_time: list[ResolutionTimeRow]
    departments: list[DepartmentRow]
    trends: list[TrendOut]
    policy_usage: list[PolicyUsageRow]


class AgentQueueItem(BaseModel):
    complaint_ref: str
    title: str
    created_at: datetime
    status: ComplaintStatus
    category_code: str | None
    subcategory_code: str | None
    department_code: str | None
    priority: str | None
    urgency: str | None
    sentiment: str | None
    escalation_level: int | None
    verification: str | None
    needs_review: bool
    sla_status: str
    resolution_due_at: datetime | None
    summary: str | None
    recommended_steps: list[str]
    suggested_response: str | None
    response_approved: bool
    escalation_warnings: list[str]


class AgentDashboardOut(BaseModel):
    department: str | None
    items: list[AgentQueueItem]


class ReportSpecOut(BaseModel):
    code: str
    title: str
    description: str


class ReportColumn(BaseModel):
    key: str
    header: str


class ReportTableOut(BaseModel):
    title: str
    columns: list[ReportColumn]
    rows: list[dict[str, Any]]
    total_rows: int


class LabelValue(BaseModel):
    label: str
    value: str | None


class ReportOut(BaseModel):
    code: str
    title: str
    description: str
    generated_at: datetime
    filters: list[LabelValue]
    summary: list[LabelValue]
    tables: list[ReportTableOut]


class EscalationLevelOut(BaseModel):
    level: int
    code: str
    name: str


class ActionOut(BaseModel):
    code: str
    kind: str
    description: str


class VocabularyOut(BaseModel):
    sentiments: list[str]
    urgencies: list[str]
    priorities: list[str]
    channels: list[str]
    follow_up_types: list[str]
    escalation_levels: list[EscalationLevelOut]
    actions: list[ActionOut]


# --- storefront ------------------------------------------------------------------------


class ProductImageOut(ORMModel):
    id: uuid.UUID

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """Public address of the image (relative to the API host)."""
        return f"/api/v1/product-images/{self.id}"


class ProductOut(ORMModel):
    sku: str
    name: str
    product_line: str
    price: float
    description: str
    specs: list[str]
    is_active: bool
    images: list[ProductImageOut]


class ProductCreate(BaseModel):
    sku: str = Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,39}$", description="e.g. VH-PHN-NX6")
    name: str = Field(min_length=2, max_length=200)
    product_line: str
    price: float = Field(gt=0, le=100_000)
    description: str = Field(min_length=2, max_length=2000)
    specs: list[str] = Field(default_factory=list, max_length=12)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    product_line: str | None = None
    price: float | None = Field(default=None, gt=0, le=100_000)
    description: str | None = Field(default=None, min_length=2, max_length=2000)
    specs: list[str] | None = Field(default=None, max_length=12)
    is_active: bool | None = None


class ImageOrderIn(BaseModel):
    image_ids: list[uuid.UUID]


class CheckoutLineIn(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=5)


class CheckoutIn(BaseModel):
    lines: list[CheckoutLineIn] = Field(min_length=1, max_length=10)
    shipping_method: Literal["standard", "express"] = "standard"
    currency: Literal["USD", "PKR", "EUR", "GBP", "AED"] = "USD"


class ShopOrderOut(ORMModel):
    order_ref: str
    checkout_ref: str | None
    product_name: str
    product_category: str
    quantity: int
    amount: float
    shipping_method: str
    order_date: date
    committed_delivery_date: date
    delivered_date: date | None
    status: str
    stage: str
    currency: str
    fx_rate: float
    amount_local: float | None
    expected_delivery_date: date | None
    next_step_at: datetime | None
    image_url: str | None = None  # the product's main image, if it has one


class SimulateIn(BaseModel):
    outcome: Literal["on_time", "late", "lost", "damaged"]
    days: int = Field(default=3, ge=0, le=30)


# --- support chat -----------------------------------------------------------------------


class ChatMessageOut(ORMModel):
    id: int
    role: str
    kind: str
    content: str
    payload: dict[str, Any]
    created_at: datetime


class ChatConversationOut(BaseModel):
    id: uuid.UUID
    state: str
    order_ref: str | None
    complaint_ref: str | None
    recent_complaint_ref: str | None = None  # the complaint a previous chat filed
    messages: list[ChatMessageOut]


class ChatStartIn(BaseModel):
    order_ref: str | None = None
    new: bool = Field(default=False, description="Close an unfinished conversation and start over")


class ChatMessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ChatOrderIn(BaseModel):
    order_ref: str | None = None


# ------------------------------------------------------------------ contact us

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
ContactTopic = Literal["order_problem", "product_question", "business", "feedback", "other"]


class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=320, pattern=EMAIL_PATTERN)
    topic: ContactTopic
    message: str = Field(min_length=10, max_length=5000)
    order_ref: str | None = Field(default=None, max_length=20)
    website: str | None = Field(default=None, description="Honeypot: leave empty")


class ContactOut(BaseModel):
    kind: Literal["complaint", "enquiry", "ignored"]
    reference: str | None


class EnquiryOut(BaseModel):
    ref: str
    name: str
    email: str
    topic: str
    message: str
    status: Literal["new", "handled"]
    created_at: datetime
    handled_at: datetime | None
    complaint_ref: str | None
    can_convert: bool


class EnquiryUpdate(BaseModel):
    status: Literal["new", "handled"]


class NewsletterIn(BaseModel):
    email: str = Field(max_length=320, pattern=EMAIL_PATTERN)
    source: str = Field(default="footer", max_length=40)


# ------------------------------------------------------------------ supporting documents


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    media_type: str
    size_bytes: int
    source: str
    created_at: datetime


# ------------------------------------------------------------------ mailbox (e-mail channel)


class MailboxStatusOut(BaseModel):
    configured: bool
    address: str | None
    last_check_at: datetime | None
    last_error: str | None


class InboundEmailOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    from_address: str
    from_name: str | None
    subject: str
    outcome: str
    reason: str | None
    via: str
    complaint_ref: str | None


class OutboundEmailOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    to_address: str
    kind: str
    subject: str
    status: str
    error: str | None
    sent_at: datetime | None
    complaint_ref: str | None


# ------------------------------------------------------------------ bulk complaint upload


class ImportRowOut(BaseModel):
    row: int  # spreadsheet row number (the header is row 1)
    status: str  # ready | warning | error
    messages: list[str]
    values: dict[str, str]
    result: str | None = None  # created | failed (after the import ran)
    reference: str | None = None
    reason: str | None = None


class ImportBatchOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str  # previewed | running | done | failed
    total: int
    created: int
    skipped: int
    failed: int
    created_at: datetime
    finished_at: datetime | None


class ImportDetailOut(ImportBatchOut):
    rows: list[ImportRowOut]


class ImportPreviewOut(ImportDetailOut):
    previously_imported: bool
    unknown_columns: list[str]


# --- run-time settings -------------------------------------------------------------------


class PolicyFactOut(BaseModel):
    fact: str
    value: str
    source: str  # document code
    version: str | None  # active version, None if the document is not active


class SettingsOut(BaseModel):
    settings: RuntimeSettings
    version: int
    updated_at: datetime | None
    updated_by: str | None
    providers_available: list[str]
    suggested_models: dict[str, list[str]]
    policy_facts: list[PolicyFactOut]
    shop_logo_url: str | None
    console_logo_url: str | None


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    email: EmailSettings
    ai: AiSettings
    operations: OperationsSettings
    orders: OrderSettings
    branding: BrandingText


class BrandingOut(BaseModel):
    shop_name: str
    shop_tagline: str
    console_name: str
    support_email: str
    phone: str
    address: str
    hours: str
    shop_logo_url: str | None
    console_logo_url: str | None


# --- currency ------------------------------------------------------------------------


class CurrencyInfo(BaseModel):
    code: str
    symbol: str
    decimals: int


class CurrencyOut(BaseModel):
    rates: dict[str, float]
    fetched_at: datetime | None
    currencies: list[CurrencyInfo]


# --- order history and returns ---------------------------------------------------------


class OrderEventOut(ORMModel):
    stage: str
    note: str | None
    actor: str
    created_at: datetime


class ReturnIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)
