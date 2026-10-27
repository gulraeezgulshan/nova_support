"""Intake, chat and import limits come from the run-time settings."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

import app_settings
from bulk_import.reader import ImportFileError, read_rows, template_csv
from complaint_processing.facts import build_facts
from complaint_processing.service import (
    ComplaintInput,
    ComplaintValidationError,
    validate_input,
)
from database.models import Complaint, Customer, CustomerType
from support_chat.intake import next_turn
from tests.fixtures.genai import ScriptedProvider
from tests.unit.test_chat_intake import ORDER, turn


def use_intake(**changes: Any) -> None:
    base = app_settings.defaults()
    app_settings.override(
        base.model_copy(update={"intake": base.intake.model_copy(update=changes)})
    )


def test_description_max_from_settings() -> None:
    use_intake(max_description_chars=500)
    with pytest.raises(ComplaintValidationError, match=r"at most 500 characters\."):
        validate_input(ComplaintInput(title="Late order", description="word " * 120))


def test_title_min_from_settings() -> None:
    use_intake(min_title_chars=10)
    data = ComplaintInput(title="Short one", description="My order arrived two weeks late.")
    with pytest.raises(ComplaintValidationError, match=r"at least 10 characters\."):
        validate_input(data)


def test_import_rows_from_settings() -> None:
    use_intake(import_max_rows=10)
    header = template_csv().decode().splitlines()[0]
    row = ",".join(["x"] * len(header.split(",")))
    rows = "\n".join([header] + [row] * 11)
    with pytest.raises(ImportFileError, match=r"At most 10 rows per file\."):
        read_rows("complaints.csv", rows.encode())


def test_chat_questions_from_settings() -> None:
    use_intake(chat_max_questions=2)
    provider = ScriptedProvider(turn())
    next_turn(provider, order=ORDER, customer_messages=["one", "two", "three"])
    assert "set ready_to_confirm to true now" in provider.requests[0].user


def _complaint(customer: Customer, created: datetime) -> Complaint:
    return Complaint(customer=customer, created_at=created, signals={}, entities={})


def test_repeat_window_from_settings() -> None:
    customer = Customer(customer_ref="CUST-1", full_name="Ann", customer_type=CustomerType.STANDARD)
    now = datetime(2026, 10, 20, 12, tzinfo=UTC)
    current = _complaint(customer, now)
    earlier = _complaint(customer, now - timedelta(days=3))
    assert build_facts(current, [earlier], date(2026, 10, 20))["repeat_count"] == 1
    use_intake(repeat_window_days=1)
    assert build_facts(current, [earlier], date(2026, 10, 20))["repeat_count"] == 0
