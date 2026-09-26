"""Hybrid retrieval over ACTIVE policy chunks (SRS Step 25).

Two independent rankings are merged with Reciprocal Rank Fusion (RRF):
semantic similarity (pgvector cosine distance) and keyword relevance (Postgres
full-text search). Keyword search catches exact policy terms and IDs that embeddings
can blur; embeddings catch paraphrases. Superseded, previous and draft versions are
excluded, so outdated policy can never be retrieved as a resolution basis.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Select, Text, cast, func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from database.models import Chunk, Document, DocumentVersion, IngestStatus, VersionStatus
from knowledge_base.config import get_kb_config
from knowledge_base.embeddings import Embedder

RRF_K = 60
CANDIDATES_PER_RANKER = 30


@dataclass(frozen=True)
class RetrievedChunk:
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


def _active_chunks_query() -> Select[int]:
    return (
        select(Chunk.id)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .where(
            DocumentVersion.status == VersionStatus.ACTIVE,
            DocumentVersion.ingest_status == IngestStatus.READY,
            Chunk.flagged.is_(False),  # quarantined passages are never used as grounding
        )
    )


def _semantic_stmt(query_vector: list[float]) -> Select[int]:
    return (
        _active_chunks_query()
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(CANDIDATES_PER_RANKER)
    )


def _keyword_stmt(query: str) -> Select[int]:
    # OR the query terms together: complaints are prose, and requiring every word (AND)
    # would almost never match. ts_rank_cd still rewards chunks matching more terms.
    ts_query = cast(
        func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|"), TSQUERY
    )
    return (
        _active_chunks_query()
        .where(Chunk.search_vector.op("@@")(ts_query))
        .order_by(func.ts_rank_cd(Chunk.search_vector, ts_query).desc())
        .limit(CANDIDATES_PER_RANKER)
    )


def _fuse(rankings: Sequence[Sequence[int]], limit: int) -> dict[int, float]:
    """Reciprocal Rank Fusion: sum of 1 / (k + rank) across rankers; keep the top `limit`."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    top = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    return {cid: scores[cid] for cid in top}


def _details_stmt(ids: Sequence[int]) -> Select[Chunk, str, str]:
    return (
        select(Chunk, Document.title, Document.doc_type)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Chunk.id.in_(ids))
    )


def _to_results(rows: Sequence[Any], scores: dict[int, float]) -> list[RetrievedChunk]:
    precedence = {t.code: t.precedence for t in get_kb_config().document_types}
    results = [
        RetrievedChunk(
            chunk_code=chunk.chunk_code,
            doc_code=chunk.doc_code,
            doc_title=title,
            doc_type=doc_type,
            precedence=precedence.get(doc_type, 99),
            version=chunk.version,
            section=chunk.section,
            heading=chunk.heading,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            content=chunk.content,
            score=round(scores[chunk.id], 6),
        )
        for chunk, title, doc_type in rows
    ]
    return sorted(results, key=lambda r: r.score, reverse=True)


async def search_chunks(
    db: AsyncSession, query: str, embedder: Embedder, limit: int = 8
) -> list[RetrievedChunk]:
    query = query.strip()
    if not query:
        return []
    query_vector = await run_in_threadpool(embedder.embed_query, query)
    semantic = (await db.scalars(_semantic_stmt(query_vector))).all()
    keyword = (await db.scalars(_keyword_stmt(query))).all()
    scores = _fuse([semantic, keyword], limit)
    if not scores:
        return []
    rows = (await db.execute(_details_stmt(list(scores)))).all()
    return _to_results(rows, scores)


def search_chunks_sync(
    db: Session, query: str, embedder: Embedder, limit: int = 8
) -> list[RetrievedChunk]:
    """Same retrieval for background workers (synchronous session)."""
    query = query.strip()
    if not query:
        return []
    query_vector = embedder.embed_query(query)
    semantic = db.scalars(_semantic_stmt(query_vector)).all()
    keyword = db.scalars(_keyword_stmt(query)).all()
    scores = _fuse([semantic, keyword], limit)
    if not scores:
        return []
    rows = db.execute(_details_stmt(list(scores))).all()
    return _to_results(rows, scores)
