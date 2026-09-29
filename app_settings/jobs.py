"""Periodic jobs on intervals set in Settings: Beat calls `tick` every 15 s."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert

from app_settings.model import RuntimeSettings
from app_settings.store import runtime
from database.models import JobRun
from database.session import sync_session
from src.core.logging import get_logger

log = get_logger(__name__)
TICK_SECONDS = 15
GRACE_SECONDS = 5  # a job due a moment after a tick still runs on that tick


@dataclass(frozen=True)
class Job:
    interval: Callable[[RuntimeSettings], int]  # seconds, from the settings
    run: Callable[[], object]


def _mailbox() -> object:
    from email_channel.tasks import check

    return check()


def _outbox() -> object:
    from email_channel.tasks import flush

    return flush()


def _sla() -> object:
    from complaint_processing.tasks import scan_sla

    return scan_sla()


def _fx() -> object:
    from storefront.currency import refresh_rates

    return refresh_rates()


JOBS: dict[str, Job] = {
    "mailbox-check": Job(lambda s: s.email.mailbox_check_seconds, _mailbox),
    "email-outbox": Job(lambda s: s.email.outbox_flush_seconds, _outbox),
    "sla-risk-scan": Job(lambda s: s.operations.sla_scan_minutes * 60, _sla),
    "fx-refresh": Job(lambda s: 12 * 3600, _fx),
}


def claim(job: str, interval_seconds: int, now: datetime | None = None) -> bool:
    """True for exactly one caller per interval (a single atomic statement)."""
    now = now or datetime.now(UTC)
    due_before = now - timedelta(seconds=max(interval_seconds - GRACE_SECONDS, 1))
    stmt = (
        insert(JobRun)
        .values(job=job, last_run_at=now)
        .on_conflict_do_update(
            index_elements=[JobRun.job],
            set_={"last_run_at": now},
            where=JobRun.last_run_at <= due_before,
        )
        .returning(JobRun.job)
    )
    with sync_session() as db:
        claimed = db.execute(stmt).scalar_one_or_none() is not None
        db.commit()
    return claimed


def tick(now: datetime | None = None, jobs: dict[str, Job] | None = None) -> list[str]:
    """Run each due job; one failing job never stops the others. Returns the jobs that ran."""
    settings, ran = runtime(), []
    for name, job in (jobs or JOBS).items():
        try:
            if claim(name, job.interval(settings), now):
                job.run()  # the gate already advanced: a failure waits for the next interval
                ran.append(name)
        except Exception:
            log.exception("scheduler.job_failed", job=name)
    return ran
