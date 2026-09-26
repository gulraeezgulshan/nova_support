"""Every shipped knowledge-base document must parse, carry complete header metadata,
and validate: the same path hidden evaluation documents will take."""

from pathlib import Path

import pytest

from complaint_rules.matrix import read_default_matrix
from document_processing.chunking import chunk_sections
from document_processing.parsers import parse_document
from document_processing.validation import build_metadata, extract_header_metadata
from knowledge_base.config import get_kb_config

GENERATED = Path(__file__).resolve().parents[2] / "sample_documents" / "generated"
DOCUMENTS = sorted(p for p in GENERATED.glob("*.*") if p.is_file())
ARCHIVE = sorted(p for p in (GENERATED / "archive").glob("*.*") if p.is_file())


def test_sample_documents_meet_srs_minimum() -> None:
    assert len(DOCUMENTS) >= 20
    assert {d.suffix for d in DOCUMENTS} >= {".pdf", ".docx"}


def test_every_rule_policy_reference_exists_in_the_documents() -> None:
    sections: dict[str, set[str]] = {}
    for path in DOCUMENTS:
        parsed = parse_document(path.read_bytes(), path.suffix.lstrip("."))
        code = path.stem.split("_", 1)[0]
        sections[code] = {s.section_number for s in parsed.sections if s.section_number}
    missing = sorted(
        ref
        for record in read_default_matrix()
        for ref in record.policy_refs
        if ref.split("#")[1] not in sections.get(ref.split("#")[0], set())
    )
    assert missing == [], f"rules cite sections that do not exist: {missing}"


@pytest.mark.parametrize("path", DOCUMENTS + ARCHIVE, ids=lambda p: p.name)
def test_sample_document_is_ingestible(path: Path) -> None:
    parsed = parse_document(path.read_bytes(), path.suffix.lstrip("."))
    header = extract_header_metadata(parsed.full_text)
    metadata = build_metadata({"title": parsed.title}, header, get_kb_config().type_codes)

    assert metadata.doc_code == path.stem.split("_", 1)[0]
    numbered = [s for s in parsed.sections if s.section_number]
    assert len(numbered) >= 4, "policy sections should be numbered for traceable citations"
    assert chunk_sections(parsed.sections)
