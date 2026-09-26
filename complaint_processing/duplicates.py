"""Near-duplicate and reworded-repeat detection (SRS Steps 52-54).

Exact duplicates are rejected at intake (content hash). Two further checks link, rather than
reject, a new complaint to an earlier one from the same customer:

- near duplicate: almost the same wording (token-set similarity), e.g. a resend
- related complaint: same issue in different words (embedding cosine similarity), e.g. a
  follow-up after an unresolved complaint
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Complaint

NEAR_DUPLICATE_MIN_RATIO = 88.0  # rapidfuzz token_set_ratio, 0-100
RELATED_MIN_SIMILARITY = 0.80  # cosine similarity of embeddings
DUPLICATE_WINDOW = timedelta(days=30)
RELATED_WINDOW = timedelta(days=120)


@dataclass(frozen=True)
class Match:
    complaint_id: uuid.UUID
    complaint_ref: str
    similarity: float  # 0-1
    kind: str  # near_duplicate | related


async def find_similar(
    db: AsyncSession,
    customer_id: uuid.UUID,
    normalized_text: str,
    embedding: list[float] | None,
    now: datetime,
    exclude_id: uuid.UUID | None = None,
) -> Match | None:
    """Best earlier match from the same customer, or None."""
    exclude = [Complaint.id != exclude_id] if exclude_id else []
    earlier = (
        await db.execute(
            select(Complaint.id, Complaint.complaint_ref, Complaint.normalized_text)
            .where(
                Complaint.customer_id == customer_id,
                Complaint.created_at >= now - DUPLICATE_WINDOW,
                Complaint.created_at <= now,
                *exclude,
            )
            .order_by(Complaint.created_at.desc())
            .limit(50)
        )
    ).all()
    best: Match | None = None
    for complaint_id, ref, text in earlier:
        ratio = fuzz.token_set_ratio(normalized_text, text)
        if ratio >= NEAR_DUPLICATE_MIN_RATIO and (best is None or ratio / 100 > best.similarity):
            best = Match(complaint_id, ref, round(ratio / 100, 3), "near_duplicate")
    if best is not None or embedding is None:
        return best

    distance = Complaint.embedding.cosine_distance(embedding)
    row = (
        await db.execute(
            select(Complaint.id, Complaint.complaint_ref, distance.label("distance"))
            .where(
                Complaint.customer_id == customer_id,
                Complaint.embedding.is_not(None),
                Complaint.created_at >= now - RELATED_WINDOW,
                Complaint.created_at <= now,
                *exclude,
            )
            .order_by(distance)
            .limit(1)
        )
    ).first()
    if row is not None and 1 - row.distance >= RELATED_MIN_SIMILARITY:
        return Match(row.id, row.complaint_ref, round(1 - row.distance, 3), "related")
    return None
