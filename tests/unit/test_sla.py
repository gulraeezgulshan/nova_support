"""SLA deadlines, risk states and the first-response / resolution clocks."""

from datetime import UTC, datetime, timedelta

import pytest

from complaint_processing.sla import (
    SlaState,
    evaluate,
    on_response_approved,
    on_status_change,
    refresh,
    schedule,
)
from database.models import Complaint, SlaPolicy

START = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
# P1: first response in 2 h, resolution in 24 h, at risk after 70% of a window.
P1 = SlaPolicy(
    priority="P1",
    name="High",
    first_response_minutes=120,
    resolution_minutes=1440,
    at_risk_threshold_pct=70,
)


def complaint(**kwargs: object) -> Complaint:
    c = Complaint(created_at=START, sla_status="pending", **kwargs)
    schedule(c, P1)
    return c


def test_deadlines_are_measured_from_submission() -> None:
    c = complaint()
    assert c.first_response_due_at == START + timedelta(hours=2)
    assert c.resolution_due_at == START + timedelta(hours=24)


def test_no_priority_means_pending() -> None:
    c = Complaint(created_at=START, sla_status="pending")
    schedule(c, None)
    assert evaluate(c, None, START + timedelta(days=9)) == SlaState.PENDING


@pytest.mark.parametrize(
    ("hours", "responded", "expected"),
    [
        (0.5, False, SlaState.ON_TRACK),
        (1.5, False, SlaState.AT_RISK),  # 75% of the 2-hour first-response window
        (3, False, SlaState.BREACHED),  # no first response within 2 hours
        (3, True, SlaState.ON_TRACK),
        (17, True, SlaState.AT_RISK),  # 70% of the 24-hour resolution window
        (25, True, SlaState.BREACHED),
    ],
)
def test_open_complaint_states(hours: float, responded: bool, expected: SlaState) -> None:
    c = complaint(first_responded_at=START + timedelta(minutes=30) if responded else None)
    assert evaluate(c, P1, START + timedelta(hours=hours)) == expected


def test_resolved_complaints_are_met_or_missed() -> None:
    on_time = complaint(resolved_at=START + timedelta(hours=20))
    late = complaint(resolved_at=START + timedelta(hours=30))
    later = START + timedelta(days=30)
    assert evaluate(on_time, P1, later) == SlaState.MET
    assert evaluate(late, P1, later) == SlaState.MISSED


def test_status_changes_start_and_stop_the_clocks() -> None:
    c = complaint()
    on_status_change(c, "assigned", START + timedelta(hours=1))
    assert c.first_responded_at == START + timedelta(hours=1)
    on_status_change(c, "in_progress", START + timedelta(hours=5))
    assert c.first_responded_at == START + timedelta(hours=1)  # the first one counts
    on_status_change(c, "resolved", START + timedelta(hours=10))
    assert c.resolved_at == START + timedelta(hours=10)
    on_status_change(c, "reopened", START + timedelta(hours=11))
    assert c.resolved_at is None


def test_an_approved_response_is_a_first_response() -> None:
    c = complaint()
    on_response_approved(c, START + timedelta(minutes=45))
    assert evaluate(c, P1, START + timedelta(hours=3)) == SlaState.ON_TRACK


def test_refresh_reports_only_changes() -> None:
    c = complaint()
    assert refresh(c, P1, START + timedelta(hours=3)) == SlaState.BREACHED
    assert refresh(c, P1, START + timedelta(hours=4)) is None
    assert c.sla_status == SlaState.BREACHED
