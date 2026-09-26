import uuid
from datetime import date

import pytest

from database.models import IngestStatus, VersionStatus
from knowledge_base.versioning import (
    VersionState,
    VersionTransitionError,
    plan_activation,
    plan_retirement,
)

TODAY = date(2026, 9, 26)


def state(
    status: VersionStatus,
    ingest: IngestStatus = IngestStatus.READY,
    expiry: date | None = None,
) -> VersionState:
    return VersionState(uuid.uuid4(), status, ingest, date(2026, 1, 1), expiry)


def test_activating_a_new_version_supersedes_the_active_one() -> None:
    old, new = state(VersionStatus.ACTIVE), state(VersionStatus.DRAFT)
    changes = plan_activation([old, new], new.id, TODAY)
    assert changes == {old.id: VersionStatus.SUPERSEDED, new.id: VersionStatus.ACTIVE}


def test_activating_the_active_version_changes_nothing() -> None:
    current = state(VersionStatus.ACTIVE)
    assert plan_activation([current], current.id, TODAY) == {}


def test_unprocessed_version_cannot_be_activated() -> None:
    pending = state(VersionStatus.DRAFT, IngestStatus.PENDING)
    with pytest.raises(VersionTransitionError, match="processed"):
        plan_activation([pending], pending.id, TODAY)


def test_expired_version_cannot_be_activated() -> None:
    expired = state(VersionStatus.DRAFT, expiry=date(2026, 6, 1))
    with pytest.raises(VersionTransitionError, match="expired"):
        plan_activation([expired], expired.id, TODAY)


def test_version_from_another_document_is_rejected() -> None:
    with pytest.raises(VersionTransitionError):
        plan_activation([state(VersionStatus.ACTIVE)], uuid.uuid4(), TODAY)


def test_retiring_marks_previous_and_requires_active() -> None:
    active = state(VersionStatus.ACTIVE)
    assert plan_retirement(active) == {active.id: VersionStatus.PREVIOUS}
    with pytest.raises(VersionTransitionError):
        plan_retirement(state(VersionStatus.SUPERSEDED))
