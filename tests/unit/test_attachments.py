"""Attachment type detection and the evidence summary."""

import pytest

from complaint_processing.attachments import describe, file_type

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 10
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 10
WEBP = b"RIFF0000WEBPVP8 " + b"0" * 10
PDF = b"%PDF-1.7\n" + b"0" * 10


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
        (WEBP, "image/webp"),
        (PDF, "application/pdf"),
        (b"PK\x03\x04zip", None),
        (b"MZ\x90\x00exe", None),
        (b"", None),
        (b"<html>%PDF-", None),
    ],
    ids=["jpeg", "png", "webp", "pdf", "zip", "exe", "empty", "pdf-not-at-start"],
)
def test_file_type_comes_from_content(data: bytes, expected: str | None) -> None:
    assert file_type(data) == expected


def test_describe_counts_photos_and_pdfs() -> None:
    assert describe([]) == "none"
    assert describe(["image/png"]) == "1 photo"
    assert describe(["image/png", "image/jpeg", "application/pdf"]) == "2 photos, 1 PDF"


def test_prompt_mentions_supporting_documents() -> None:
    from genai_pipeline.prompts import load_template

    template = load_template("complaint_analysis")
    assert template.version == "1.2.0"
    assert "Supporting documents: {{ supporting_documents }}" in template.user


def test_evidence_check_is_informational() -> None:
    from python_validation.checks import evidence_check
    from python_validation.types import CheckStatus

    check = evidence_check(["image/png", "application/pdf"])
    assert check.code == "evidence" and check.status == CheckStatus.SKIP
    assert "1 photo, 1 PDF" in check.message
    assert "No supporting documents" in evidence_check([]).message
