"""Split parsed sections into retrieval-sized chunks (SRS Step 6).

Chunks never cross a section boundary, so every chunk has exactly one section number
and heading. Long sections are split on paragraph, then sentence, boundaries with a
small overlap so a rule is never cut away from its context.
"""

import re
from dataclasses import dataclass

from document_processing.parsers import Paragraph, Section

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    section: str | None
    heading: str | None
    page_start: int | None
    page_end: int | None
    content: str
    token_count: int

    @property
    def embedding_text(self) -> str:
        """Text sent to the embedding model: the heading adds useful context."""
        return f"{self.heading}\n{self.content}" if self.heading else self.content


def estimate_tokens(text: str) -> int:
    """Cheap, model-independent estimate (~1.3 tokens per English word)."""
    return max(1, round(len(text.split()) * 1.3))


def chunk_sections(
    sections: list[Section], max_tokens: int = 450, overlap_tokens: int = 60
) -> list[ChunkDraft]:
    if overlap_tokens >= max_tokens:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    drafts: list[ChunkDraft] = []
    for section in sections:
        for pieces in _pack(
            _split_units(section.paragraphs, max_tokens), max_tokens, overlap_tokens
        ):
            content = "\n\n".join(p.text for p in pieces).strip()
            if not content:
                continue
            pages = [p.page for p in pieces if p.page is not None]
            drafts.append(
                ChunkDraft(
                    ordinal=len(drafts) + 1,
                    section=section.section_number,
                    heading=section.heading,
                    page_start=min(pages) if pages else None,
                    page_end=max(pages) if pages else None,
                    content=content,
                    token_count=estimate_tokens(content),
                )
            )
    return drafts


def _split_units(paragraphs: list[Paragraph], max_tokens: int) -> list[Paragraph]:
    """Break paragraphs that are too long on their own into sentence groups."""
    units: list[Paragraph] = []
    for paragraph in paragraphs:
        if estimate_tokens(paragraph.text) <= max_tokens:
            units.append(paragraph)
            continue
        current: list[str] = []
        for sentence in SENTENCE_END.split(paragraph.text):
            candidate = " ".join([*current, sentence])
            if current and estimate_tokens(candidate) > max_tokens:
                units.append(Paragraph(" ".join(current), paragraph.page))
                current = [sentence]
            else:
                current.append(sentence)
        if current:
            units.append(Paragraph(" ".join(current), paragraph.page))
    return units


def _pack(units: list[Paragraph], max_tokens: int, overlap_tokens: int) -> list[list[Paragraph]]:
    """Greedily pack units into groups under max_tokens, repeating a small tail as overlap."""
    groups: list[list[Paragraph]] = []
    current: list[Paragraph] = []
    current_tokens = 0
    for unit in units:
        unit_tokens = estimate_tokens(unit.text)
        if current and current_tokens + unit_tokens > max_tokens:
            groups.append(current)
            overlap = _tail(current, overlap_tokens)
            # Only carry the overlap if the next unit still fits with it.
            if overlap and estimate_tokens(overlap.text) + unit_tokens <= max_tokens:
                current = [overlap]
                current_tokens = estimate_tokens(overlap.text)
            else:
                current, current_tokens = [], 0
        current.append(unit)
        current_tokens += unit_tokens
    if current:
        groups.append(current)
    return groups


def _tail(group: list[Paragraph], overlap_tokens: int) -> Paragraph | None:
    if overlap_tokens <= 0 or not group:
        return None
    last = group[-1]
    sentences = SENTENCE_END.split(last.text)
    tail: list[str] = []
    for sentence in reversed(sentences):
        if tail and estimate_tokens(" ".join([sentence, *tail])) > overlap_tokens:
            break
        tail.insert(0, sentence)
    if len(tail) == len(sentences):  # the whole paragraph would repeat; not useful overlap
        return None
    return Paragraph(" ".join(tail), last.page)
