from itertools import pairwise

import pytest

from document_processing.chunking import chunk_sections, estimate_tokens
from document_processing.parsers import Paragraph, Section


def sentence(i: int) -> str:
    return f"Rule {i} requires the agent to verify the order before approving any refund."


def test_short_sections_become_one_chunk_each_and_never_merge() -> None:
    sections = [
        Section("1 Purpose", "1", 2, [Paragraph("Short purpose.", 1)]),
        Section("2 Scope", "2", 2, [Paragraph("Short scope.", 2)]),
    ]
    chunks = chunk_sections(sections, max_tokens=100, overlap_tokens=10)
    assert [(c.section, c.page_start, c.content) for c in chunks] == [
        ("1", 1, "Short purpose."),
        ("2", 2, "Short scope."),
    ]
    assert [c.ordinal for c in chunks] == [1, 2]


def test_long_section_is_split_under_the_limit_with_overlap() -> None:
    paragraphs = [
        Paragraph(" ".join(sentence(i) for i in range(p * 4, p * 4 + 4)), p + 1) for p in range(6)
    ]
    chunks = chunk_sections([Section("5 Refunds", "5", 2, paragraphs)], 120, 20)

    assert len(chunks) > 1
    assert all(c.token_count <= 120 for c in chunks)
    assert all(c.section == "5" and c.heading == "5 Refunds" for c in chunks)
    # Consecutive chunks share some text (overlap), so no rule loses its context.
    for previous, current in pairwise(chunks):
        carried_over = current.content.split("\n\n")[0]
        assert carried_over in previous.content
    # Page range follows the paragraphs that ended up in each chunk.
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 6


def test_single_huge_paragraph_is_split_by_sentences() -> None:
    huge = Paragraph(" ".join(sentence(i) for i in range(60)), 3)
    chunks = chunk_sections([Section(None, None, 0, [huge])], 150, 0)
    assert len(chunks) > 3
    assert all(estimate_tokens(c.content) <= 150 for c in chunks)


def test_embedding_text_includes_heading() -> None:
    [chunk] = chunk_sections([Section("7 Warranty", "7", 2, [Paragraph("One year.", None)])])
    assert chunk.embedding_text == "7 Warranty\nOne year."


def test_overlap_must_be_smaller_than_limit() -> None:
    with pytest.raises(ValueError):
        chunk_sections([], max_tokens=50, overlap_tokens=50)
