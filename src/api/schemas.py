"""Request/response models for the HTTP API (these drive the generated TypeScript client)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from database.models import IngestStatus, Role, VersionStatus


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
