"""Policy version lifecycle rules (SRS Step 7), as pure functions.

Only one version of a document may be ACTIVE. Activating a version supersedes the old
active one; retiring an active version without a replacement marks it PREVIOUS.
Outdated versions stay stored for traceability but are never used as the basis
for a resolution.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from database.models.knowledge_base import DocumentVersion, IngestStatus, VersionStatus


class VersionTransitionError(Exception):
    pass


@dataclass(frozen=True)
class VersionState:
    id: uuid.UUID
    status: VersionStatus
    ingest_status: IngestStatus
    effective_date: date
    expiry_date: date | None


def plan_activation(
    versions: list[VersionState], target_id: uuid.UUID, today: date
) -> dict[uuid.UUID, VersionStatus]:
    """Return the status changes needed to make `target_id` the active version."""
    target = next((v for v in versions if v.id == target_id), None)
    if target is None:
        raise VersionTransitionError("Version does not belong to this document.")
    if target.status == VersionStatus.ACTIVE:
        return {}
    if target.ingest_status != IngestStatus.READY:
        raise VersionTransitionError("Only fully processed versions can be activated.")
    if target.expiry_date is not None and target.expiry_date < today:
        raise VersionTransitionError("An expired version cannot be activated.")

    changes = {v.id: VersionStatus.SUPERSEDED for v in versions if v.status == VersionStatus.ACTIVE}
    changes[target_id] = VersionStatus.ACTIVE
    return changes


def plan_retirement(version: VersionState) -> dict[uuid.UUID, VersionStatus]:
    if version.status != VersionStatus.ACTIVE:
        raise VersionTransitionError("Only the active version can be retired.")
    return {version.id: VersionStatus.PREVIOUS}


def to_state(version: DocumentVersion) -> VersionState:
    return VersionState(
        id=version.id,
        status=version.status,
        ingest_status=version.ingest_status,
        effective_date=version.effective_date,
        expiry_date=version.expiry_date,
    )
