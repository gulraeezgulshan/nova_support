"""Validation of uploaded knowledge-base files and their metadata (SRS Step 4).

Checks: file type (by content, not just extension), size, empty files, document ID,
version, effective/expiry dates and document category. Duplicate detection needs the
database and lives in the knowledge-base service.
"""

import hashlib
import io
import re
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, ValidationError, field_validator, model_validator

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": DOCX_MEDIA_TYPE,
    "txt": "text/plain",
    "md": "text/markdown",
}
FILE_TYPE_BY_MEDIA_TYPE = {v: k for k, v in MEDIA_TYPES.items()}

DOC_CODE_PATTERN = re.compile(r"^[A-Z]{2,6}(-[A-Z0-9]{2,8}){1,3}$")  # e.g. DEL-POL-04
VERSION_PATTERN = re.compile(r"^\d{1,3}(\.\d{1,3}){0,2}$")  # 1, 1.2, 1.2.3


@dataclass
class DocumentValidationError(Exception):
    issues: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return "; ".join(self.issues)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_file_type(filename: str, data: bytes, max_bytes: int) -> str:
    """Return the file type key (pdf/docx/txt/md) or raise DocumentValidationError."""
    if not data:
        raise DocumentValidationError(["File is empty."])
    if len(data) > max_bytes:
        raise DocumentValidationError(
            [f"File is {len(data) / 1_048_576:.1f} MB; the limit is {max_bytes // 1_048_576} MB."]
        )

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in MEDIA_TYPES:
        allowed = ", ".join(sorted(MEDIA_TYPES))
        raise DocumentValidationError(
            [f"Unsupported file type '.{extension}'. Allowed: {allowed}."]
        )

    if not _content_matches(extension, data):
        raise DocumentValidationError(
            [f"File content does not match its '.{extension}' extension (possibly corrupt)."]
        )
    return extension


def _content_matches(extension: str, data: bytes) -> bool:
    if extension == "pdf":
        return data.lstrip()[:5] == b"%PDF-"
    if extension == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return "word/document.xml" in archive.namelist()
        except zipfile.BadZipFile:
            return False
    # Plain text / Markdown: must be UTF-8 and contain no binary NUL bytes.
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"\x00" not in data


class DocumentMetadata(BaseModel):
    doc_code: str
    title: str
    doc_type: str
    version: str
    effective_date: date
    expiry_date: date | None = None

    @field_validator("doc_code")
    @classmethod
    def _doc_code(cls, value: str) -> str:
        value = value.strip().upper()
        if not DOC_CODE_PATTERN.match(value):
            raise ValueError("must look like 'DEL-POL-04' (uppercase letters, digits, hyphens)")
        return value

    @field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        value = value.strip().lstrip("vV")
        if not VERSION_PATTERN.match(value):
            raise ValueError("must be numeric, e.g. '1', '2.1' or '2.1.0'")
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("is too short")
        return value[:255]

    @field_validator("doc_type")
    @classmethod
    def _doc_type(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_").replace("-", "_")

    @model_validator(mode="after")
    def _dates(self) -> "DocumentMetadata":
        if self.expiry_date and self.expiry_date <= self.effective_date:
            raise ValueError("expiry_date must be after effective_date")
        return self


def build_metadata(
    form: Mapping[str, str | None],
    header: Mapping[str, str],
    allowed_doc_types: set[str],
) -> DocumentMetadata:
    """Merge form fields with metadata found in the document header, then validate.

    Values typed in the form win, but if the document header states a different
    document ID or version, the upload is rejected instead of silently mislabelled.
    """
    issues: list[str] = []
    merged: dict[str, str] = {}
    for key in ("doc_code", "title", "doc_type", "version", "effective_date", "expiry_date"):
        form_value = (form.get(key) or "").strip()
        header_value = (header.get(key) or "").strip()
        if (
            key in ("doc_code", "version")
            and form_value
            and header_value
            and _normalise(form_value) != _normalise(header_value)
        ):
            issues.append(
                f"{key}: form value '{form_value}' does not match document header '{header_value}'."
            )
        value = form_value or header_value
        if value:
            merged[key] = value

    for required in ("doc_code", "title", "doc_type", "version", "effective_date"):
        if required not in merged:
            issues.append(f"{required}: missing (not in form and not found in document header).")
    if issues:
        raise DocumentValidationError(issues)

    try:
        metadata = DocumentMetadata.model_validate(merged)
    except ValidationError as exc:
        raise DocumentValidationError(
            [
                f"{'.'.join(str(p) for p in err['loc']) or 'metadata'}: {err['msg']}"
                for err in exc.errors()
            ]
        ) from exc

    if metadata.doc_type not in allowed_doc_types:
        raise DocumentValidationError(
            [
                f"doc_type: '{metadata.doc_type}' is not an allowed document category "
                f"({', '.join(sorted(allowed_doc_types))})."
            ]
        )
    return metadata


def _normalise(value: str) -> str:
    return value.strip().upper().lstrip("V")


_HEADER_FIELDS = {
    "doc_code": r"document\s*(?:id|code|number)",
    "title": r"(?:document\s*)?title",
    "doc_type": r"document\s*(?:type|category)",
    "version": r"version",
    "effective_date": r"effective\s*(?:date|from)",
    "expiry_date": r"(?:expiry|expiration|review)\s*date",
}
_HEADER_PATTERNS = {
    key: re.compile(rf"^\s*\|?\s*{label}\s*[:|]\s*(.+?)\s*\|?\s*$", re.IGNORECASE | re.MULTILINE)
    for key, label in _HEADER_FIELDS.items()
}


def extract_header_metadata(text: str, max_chars: int = 3000) -> dict[str, str]:
    """Find 'Document ID: DEL-POL-04'-style lines near the top of a document."""
    head = text[:max_chars]
    found: dict[str, str] = {}
    for key, pattern in _HEADER_PATTERNS.items():
        match = pattern.search(head)
        if match:
            found[key] = match.group(1).strip()
    for key in ("effective_date", "expiry_date"):
        if key in found:
            parsed = parse_date(found[key])
            if parsed is None:
                found.pop(key)
            else:
                found[key] = parsed.isoformat()
    return found


def parse_date(value: str) -> date | None:
    value = value.strip()
    for pattern in (r"^(\d{4})-(\d{2})-(\d{2})$", r"^(\d{2})/(\d{2})/(\d{4})$"):
        match = re.match(pattern, value)
        if match:
            parts = [int(p) for p in match.groups()]
            year, month, day = parts if len(str(parts[0])) == 4 else (parts[2], parts[1], parts[0])
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None
