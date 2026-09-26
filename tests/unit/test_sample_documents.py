"""Every shipped knowledge-base document must parse, carry complete header metadata,
and validate: the same path hidden evaluation documents will take."""

from pathlib import Path

import pytest

from document_processing.chunking import chunk_sections
from document_processing.parsers import parse_document
from document_processing.validation import build_metadata, extract_header_metadata
from knowledge_base.config import get_kb_config

GENERATED = Path(__file__).resolve().parents[2] / "sample_documents" / "generated"
DOCUMENTS = sorted(GENERATED.glob("*.*"))


def test_sample_documents_exist() -> None:
    assert len(DOCUMENTS) >= 7
    assert {d.suffix for d in DOCUMENTS} >= {".pdf", ".docx"}


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda p: p.name)
def test_sample_document_is_ingestible(path: Path) -> None:
    parsed = parse_document(path.read_bytes(), path.suffix.lstrip("."))
    header = extract_header_metadata(parsed.full_text)
    metadata = build_metadata({"title": parsed.title}, header, get_kb_config().type_codes)

    assert metadata.doc_code == path.stem.split("_", 1)[0]
    numbered = [s for s in parsed.sections if s.section_number]
    assert len(numbered) >= 4, "policy sections should be numbered for traceable citations"
    assert chunk_sections(parsed.sections)
