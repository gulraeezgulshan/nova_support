from datetime import date
from typing import ClassVar

import pytest

from document_processing.validation import (
    DocumentValidationError,
    build_metadata,
    detect_file_type,
    extract_header_metadata,
)
from tests.fixtures.documents import DELIVERY_HEADER, DELIVERY_SECTIONS, make_docx, make_pdf

MB = 1024 * 1024
TYPES = {"policy", "faq", "sop"}


class TestDetectFileType:
    def test_accepts_real_pdf_and_docx(self) -> None:
        assert detect_file_type("a.pdf", make_pdf([("Hello", 11, False)]), MB) == "pdf"
        assert (
            detect_file_type("a.DOCX", make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS), MB) == "docx"
        )

    def test_rejects_empty_file(self) -> None:
        with pytest.raises(DocumentValidationError, match="empty"):
            detect_file_type("a.pdf", b"", MB)

    def test_rejects_oversized_file(self) -> None:
        with pytest.raises(DocumentValidationError, match="limit"):
            detect_file_type("a.txt", b"x" * (MB + 1), MB)

    def test_rejects_unsupported_extension(self) -> None:
        with pytest.raises(DocumentValidationError, match="Unsupported"):
            detect_file_type("a.exe", b"MZ...", MB)

    def test_rejects_content_that_does_not_match_extension(self) -> None:
        with pytest.raises(DocumentValidationError, match="does not match"):
            detect_file_type("policy.pdf", b"just text", MB)
        with pytest.raises(DocumentValidationError, match="does not match"):
            detect_file_type("policy.docx", b"PK not really a zip", MB)
        with pytest.raises(DocumentValidationError, match="does not match"):
            detect_file_type("notes.txt", b"\x00\x01binary", MB)


class TestHeaderMetadata:
    def test_reads_labelled_lines_and_normalises_dates(self) -> None:
        text = (
            "Refund Policy\nDocument ID: REF-POL-01\nDocument Type: policy\n"
            "Version: 2.1\nEffective Date: 15/03/2026\nExpiry Date: 2027-03-15\n"
        )
        assert extract_header_metadata(text) == {
            "doc_code": "REF-POL-01",
            "doc_type": "policy",
            "version": "2.1",
            "effective_date": "2026-03-15",
            "expiry_date": "2027-03-15",
        }

    def test_ignores_invalid_dates(self) -> None:
        assert "effective_date" not in extract_header_metadata("Effective Date: 31/02/2026")


class TestBuildMetadata:
    header: ClassVar[dict[str, str]] = {
        "doc_code": "DEL-POL-04",
        "title": "Delivery Policy",
        "doc_type": "policy",
        "version": "1.0",
        "effective_date": "2026-01-01",
    }

    def test_header_alone_is_enough(self) -> None:
        metadata = build_metadata({}, self.header, TYPES)
        assert metadata.doc_code == "DEL-POL-04"
        assert metadata.effective_date == date(2026, 1, 1)

    def test_form_values_are_normalised(self) -> None:
        form = {**self.header, "doc_code": "del-pol-04", "version": "v1.0"}
        metadata = build_metadata(form, {}, TYPES)
        assert (metadata.doc_code, metadata.version) == ("DEL-POL-04", "1.0")

    def test_form_and_header_disagreeing_on_id_is_rejected(self) -> None:
        with pytest.raises(DocumentValidationError, match="does not match document header"):
            build_metadata({"doc_code": "DEL-POL-05"}, self.header, TYPES)

    def test_missing_required_fields_are_all_reported(self) -> None:
        with pytest.raises(DocumentValidationError) as info:
            build_metadata({"title": "Something"}, {}, TYPES)
        assert len(info.value.issues) == 4  # doc_code, doc_type, version, effective_date

    def test_unknown_document_category_is_rejected(self) -> None:
        with pytest.raises(DocumentValidationError, match="not an allowed document category"):
            build_metadata({**self.header, "doc_type": "memo"}, {}, TYPES)

    def test_expiry_must_follow_effective_date(self) -> None:
        with pytest.raises(DocumentValidationError, match="expiry_date must be after"):
            build_metadata({**self.header, "expiry_date": "2025-12-31"}, {}, TYPES)

    @pytest.mark.parametrize("bad_code", ["delivery", "D-1", "DEL POL 04", "DEL-"])
    def test_malformed_document_ids_are_rejected(self, bad_code: str) -> None:
        with pytest.raises(DocumentValidationError, match="doc_code"):
            build_metadata({**self.header, "doc_code": bad_code}, {}, TYPES)
