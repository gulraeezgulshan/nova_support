"""One Beat tick every 15 s; each job runs once per its configured interval."""

from datetime import UTC, datetime, timedelta

import pytest

from app_settings.jobs import Job, claim, tick

pytestmark = pytest.mark.db
T0 = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def test_claim_once_per_interval(clean_db: None) -> None:
    assert claim("mailbox-check", 60, T0)
    assert not claim("mailbox-check", 60, T0 + timedelta(seconds=30))
    assert claim("mailbox-check", 60, T0 + timedelta(seconds=60))


def test_tick_runs_only_due_jobs_and_survives_a_failure(clean_db: None) -> None:
    ran: list[str] = []

    def boom() -> None:
        raise RuntimeError("mail server down")

    jobs = {
        "a": Job(lambda s: 60, lambda: ran.append("a")),
        "broken": Job(lambda s: 60, boom),
        "b": Job(lambda s: 300, lambda: ran.append("b")),
    }
    assert tick(T0, jobs) == ["a", "b"]
    assert tick(T0 + timedelta(seconds=15), jobs) == []  # nothing due, broken not retried
    assert tick(T0 + timedelta(seconds=60), jobs) == ["a"]


def test_beat_schedules_only_the_tick() -> None:
    from src.worker import celery_app

    schedule = {v["task"]: v["schedule"] for v in celery_app.conf.beat_schedule.values()}
    assert schedule == {"app_settings.tasks.tick": 15.0}
    assert "app_settings.tasks" in celery_app.conf.include
