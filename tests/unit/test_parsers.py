import pytest

from document_processing.parsers import ParseError, parse_document
from tests.fixtures.documents import DELIVERY_HEADER, DELIVERY_SECTIONS, make_docx, make_pdf


def test_pdf_sections_headings_and_pages() -> None:
    data = make_pdf(
        [
            ("Delivery Policy", 20, True),
            ("Document ID: DEL-POL-04", 11, False),
            ("1 Purpose", 14, True),
            ("This policy defines delivery commitments.", 11, False),
            None,  # page break
            ("5.2 Late Delivery Compensation", 14, True),
            ("Orders more than 5 business days late get a 10% store credit.", 11, False),
        ]
    )
    parsed = parse_document(data, "pdf")

    assert parsed.page_count == 2
    assert [s.heading for s in parsed.sections] == [
        "Delivery Policy",
        "1 Purpose",
        "5.2 Late Delivery Compensation",
    ]
    late = parsed.sections[-1]
    assert late.section_number == "5.2"
    assert late.page_start == late.page_end == 2
    assert "Page 1 of 2" not in parsed.full_text  # page footers are dropped
    assert "Document ID: DEL-POL-04" in parsed.full_text


def test_docx_heading_styles_become_sections() -> None:
    parsed = parse_document(make_docx(DELIVERY_HEADER, DELIVERY_SECTIONS), "docx")

    assert parsed.title == "Delivery Policy"
    headings = [s.heading for s in parsed.sections]
    assert headings == ["Delivery Policy", "1 Purpose", "5.2 Late Delivery Compensation"]
    assert parsed.sections[2].section_number == "5.2"
    assert parsed.sections[2].page_start is None  # DOCX has no fixed pages
    assert len(parsed.sections[2].paragraphs) == 2


def test_markdown_headings_and_numbered_text_headings() -> None:
    text = (
        "# Refund Policy\n\nIntro line.\n\n## 3 Eligibility\n\nItems must be unused.\n\n"
        "4.1 Timelines\nRefunds take 7 days.\n"
    )
    parsed = parse_document(text.encode(), "md")
    assert [(s.heading, s.section_number) for s in parsed.sections] == [
        ("Refund Policy", None),
        ("3 Eligibility", "3"),
        ("4.1 Timelines", "4.1"),
    ]


def test_corrupt_pdf_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_document(b"%PDF-1.7 garbage", "pdf")


def test_ligatures_and_full_width_characters_are_normalised() -> None:
    from document_processing.parsers import normalise_text

    raw = "E\ufb00ective  Date:\u00a0\uff12\uff10\uff12\uff16"  # ligature, NBSP, full-width
    assert normalise_text(raw) == "Effective Date: 2026"


def test_consecutive_label_lines_stay_separate_paragraphs() -> None:
    text = "# Policy\nDocument ID: REF-POL-01\nVersion: 3.1\nEffective Date: 2026-03-01\n"
    parsed = parse_document(text.encode(), "md")
    assert [p.text for p in parsed.sections[0].paragraphs] == [
        "Document ID: REF-POL-01",
        "Version: 3.1",
        "Effective Date: 2026-03-01",
    ]
