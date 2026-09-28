"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from database.models.analysis import AnalysisRun, LlmCall, PromptVersion, RunStatus
from database.models.attachments import ComplaintAttachment
from database.models.audit import AuditEvent
from database.models.chat import ChatConversation, ChatMessage, ChatState
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
from database.models.contact import ENQUIRY_REF_SEQ, Enquiry, EnquiryStatus, NewsletterSubscriber
from database.models.email import InboundEmail, MailboxState, OutboundEmail
from database.models.imports import ImportBatch
from database.models.knowledge_base import (
    Chunk,
    Document,
    DocumentVersion,
    IngestStatus,
    VersionStatus,
)
from database.models.rules import Rule, RuleType
from database.models.settings import AppSettingsRow, JobRun
from database.models.storefront import CHECKOUT_REF_SEQ, ORDER_REF_SEQ, Product, ProductImage
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
    "CHECKOUT_REF_SEQ",
    "COMPLAINT_REF_SEQ",
    "CUSTOMER_REF_SEQ",
    "ENQUIRY_REF_SEQ",
    "ORDER_REF_SEQ",
    "AnalysisRun",
    "AppSettingsRow",
    "AuditEvent",
    "Category",
    "ChatConversation",
    "ChatMessage",
    "ChatState",
    "Chunk",
    "Complaint",
    "ComplaintAttachment",
    "ComplaintEvent",
    "ComplaintStatus",
    "Customer",
    "CustomerType",
    "Department",
    "Document",
    "DocumentVersion",
    "Enquiry",
    "EnquiryStatus",
    "ImportBatch",
    "InboundEmail",
    "IngestStatus",
    "JobRun",
    "LlmCall",
    "MailboxState",
    "NewsletterSubscriber",
    "Order",
    "OutboundEmail",
    "Product",
    "ProductImage",
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
