"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from database.models.analysis import AnalysisRun, LlmCall, PromptVersion, RunStatus
from database.models.audit import AuditEvent
from database.models.complaints import (
    COMPLAINT_REF_SEQ,
    CUSTOMER_REF_SEQ,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Customer,
    CustomerType,
    Order,
)
from database.models.knowledge_base import (
    Chunk,
    Document,
    DocumentVersion,
    IngestStatus,
    VersionStatus,
)
from database.models.rules import Rule, RuleType
from database.models.taxonomy import Category, Department, SlaPolicy, Subcategory
from database.models.user import Role, User
from database.models.validation import (
    ReviewAction,
    ReviewerDecision,
    ReviewStatus,
    ReviewTask,
    ValidationRun,
)

__all__ = [
    "COMPLAINT_REF_SEQ",
    "CUSTOMER_REF_SEQ",
    "AnalysisRun",
    "AuditEvent",
    "Category",
    "Chunk",
    "Complaint",
    "ComplaintEvent",
    "ComplaintStatus",
    "Customer",
    "CustomerType",
    "Department",
    "Document",
    "DocumentVersion",
    "IngestStatus",
    "LlmCall",
    "Order",
    "PromptVersion",
    "ReviewAction",
    "ReviewStatus",
    "ReviewTask",
    "ReviewerDecision",
    "Role",
    "Rule",
    "RuleType",
    "RunStatus",
    "SlaPolicy",
    "Subcategory",
    "User",
    "ValidationRun",
    "VersionStatus",
]
