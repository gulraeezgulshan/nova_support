"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from database.models.audit import AuditEvent
from database.models.knowledge_base import (
    Chunk,
    Document,
    DocumentVersion,
    IngestStatus,
    VersionStatus,
)
from database.models.taxonomy import Category, Department, SlaPolicy, Subcategory
from database.models.user import Role, User

__all__ = [
    "AuditEvent",
    "Category",
    "Chunk",
    "Department",
    "Document",
    "DocumentVersion",
    "IngestStatus",
    "Role",
    "SlaPolicy",
    "Subcategory",
    "User",
    "VersionStatus",
]
