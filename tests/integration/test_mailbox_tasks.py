"""Scheduled mailbox check and outbox flush, with fake IMAP and SMTP."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import select, text

from database.models import Complaint, InboundEmail, MailboxState, OutboundEmail
from database.session import get_sync_engine, sync_session
from email_channel import tasks
from src.core.config import Settings, get_settings
from tests.emails import build

pytestmark = pytest.mark.db

BODY = "My tablet arrived with a cracked screen and the box was crushed in transit."


def configured() -> Settings:
    return get_settings().model_copy(
        update={
            "mail_imap_host": "imap.test",
            "mail_smtp_host": "smtp.test",
            "mail_username": "care@volthaven.test",
            "mail_password": "app-password",
        }
    )


class FakeMailbox:
    def __init__(self, messages: list[bytes]):
        self.messages = {str(i).encode(): m for i, m in enumerate(messages, 1)}
        self.seen: list[bytes] = []

    def unseen(self, limit: int) -> list[tuple[bytes, bytes]]:
        return [(u, m) for u, m in self.messages.items() if u not in self.seen][:limit]

    def mark_seen(self, uid: bytes) -> None:
        self.seen.append(uid)

    def close(self) -> None:
        pass


class FakeSender:
    sent: list[EmailMessage] = []  # noqa: RUF012 - shared by the fake's instances on purpose
    fail = False

    def __init__(self, settings: Settings):
        pass

    def send(self, message: EmailMessage) -> None:
        if FakeSender.fail:
            raise OSError("SMTP down")
        FakeSender.sent.append(message)


@pytest.fixture(autouse=True)
def _reset(clean_db: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from complaint_processing import service

    FakeSender.sent, FakeSender.fail = [], False
    monkeypatch.setattr(service, "enqueue_analysis", lambda *_: None)
    yield


def test_not_configured_does_nothing() -> None:
    box = FakeMailbox([build(text=BODY)])
    assert tasks.check(lambda s: box, get_settings()) == {"status": "not_configured"}
    assert box.seen == []


def test_check_files_mail_marks_seen_and_records_the_run() -> None:
    auto = build(text="Out of office", message_id="<o@x>", headers={"Auto-Submitted": "auto"})
    box = FakeMailbox([build(text=BODY), auto])
    assert tasks.check(lambda s: box, configured()) == {"status": "ok", "processed": 2}
    assert sorted(box.seen) == [b"1", b"2"]
    with sync_session() as db:
        assert {r.outcome for r in db.scalars(select(InboundEmail))} == {"filed", "ignored"}
        assert {r.via for r in db.scalars(select(InboundEmail))} == {"imap"}
        state = db.get(MailboxState, 1)
        assert state is not None and state.last_check_at and state.last_error is None


def test_check_is_skipped_while_another_run_holds_the_lock() -> None:
    with get_sync_engine().connect() as conn:
        conn.execute(text("select pg_advisory_lock(:k)"), {"k": tasks.LOCK_KEY})
        try:
            assert tasks.check(lambda s: FakeMailbox([]), configured()) == {"status": "locked"}
        finally:
            conn.execute(text("select pg_advisory_unlock(:k)"), {"k": tasks.LOCK_KEY})


def test_a_failing_message_is_retried_then_given_up(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*_: object, **__: object) -> str:
        raise RuntimeError("parser exploded")

    box = FakeMailbox([build(text=BODY)])
    monkeypatch.setattr(tasks, "_process_one", boom)
    for _ in range(2):
        tasks.check(lambda s: box, configured())
        assert box.seen == []  # left unread for the next run
    tasks.check(lambda s: box, configured())
    assert box.seen == [b"1"]  # third failure: marked read, recorded as failed
    with sync_session() as db:
        record = db.scalars(select(InboundEmail)).one()
        assert record.outcome == "failed" and record.attempts == 3
        state = db.get(MailboxState, 1)
        assert state is not None and "parser exploded" in (state.last_error or "")


def test_login_failure_is_recorded() -> None:
    def refuse(settings: Settings) -> FakeMailbox:
        raise OSError("authentication failed")

    assert tasks.check(refuse, configured())["status"] == "error"
    with sync_session() as db:
        state = db.get(MailboxState, 1)
        assert state is not None and "authentication failed" in (state.last_error or "")


def test_flush_sends_with_thread_headers_and_retries() -> None:
    tasks.check(lambda s: FakeMailbox([build(text=BODY)]), configured())
    FakeSender.fail = True
    now = datetime.now(UTC)
    assert tasks.flush(FakeSender, configured(), now) == {"sent": 0, "failed": 1}
    with sync_session() as db:
        email = db.scalars(select(OutboundEmail)).one()
        assert email.status == "queued" and email.attempts == 1 and email.next_attempt_at
    assert tasks.flush(FakeSender, configured(), now) == {"sent": 0, "failed": 0}  # not due
    FakeSender.fail = False
    later = now + timedelta(hours=1)
    assert tasks.flush(FakeSender, configured(), later) == {"sent": 1, "failed": 0}
    [message] = FakeSender.sent
    assert message["To"] == "sara@example.test"
    assert message["In-Reply-To"] == "<m1@example.test>"
    assert "[CMP-" in message["Subject"]
    assert message["From"] == "VoltHaven Customer Care <care@volthaven.test>"
    assert message["Auto-Submitted"] == "auto-replied"  # stops other auto-responders looping
    with sync_session() as db:
        email = db.scalars(select(OutboundEmail)).one()
        assert email.status == "sent" and email.sent_at


def test_flush_gives_up_after_three_attempts() -> None:
    tasks.check(lambda s: FakeMailbox([build(text=BODY)]), configured())
    FakeSender.fail = True
    now = datetime.now(UTC)
    for hours in (0, 1, 2):
        tasks.flush(FakeSender, configured(), now + timedelta(hours=hours))
    with sync_session() as db:
        email = db.scalars(select(OutboundEmail)).one()
        assert (
            email.status == "failed" and email.attempts == 3 and "SMTP down" in (email.error or "")
        )


def test_flush_uses_the_configured_sender_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    tasks.check(lambda s: FakeMailbox([build(text=BODY)]), configured())
    chosen: list[Settings] = []

    def factory(settings: Settings) -> FakeSender:
        chosen.append(settings)
        return FakeSender(settings)

    monkeypatch.setattr(tasks, "get_sender", factory)
    assert tasks.flush(settings=configured()) == {"sent": 1, "failed": 0}
    assert len(chosen) == 1 and len(FakeSender.sent) == 1


def test_failed_emails_can_be_queued_again_once_sending_works() -> None:
    tasks.check(lambda s: FakeMailbox([build(text=BODY)]), configured())
    FakeSender.fail = True
    now = datetime.now(UTC)
    for hours in (0, 1, 2):
        tasks.flush(FakeSender, configured(), now + timedelta(hours=hours))
    FakeSender.fail = False

    assert tasks.retry_failed() == 1
    assert tasks.flush(FakeSender, configured(), now + timedelta(hours=3)) == {
        "sent": 1,
        "failed": 0,
    }
    with sync_session() as db:
        email = db.scalars(select(OutboundEmail)).one()
        assert email.status == "sent" and email.error is None
    assert tasks.retry_failed() == 0  # nothing left to retry


def test_flush_without_settings_marks_not_configured() -> None:
    tasks.check(lambda s: FakeMailbox([build(text=BODY)]), configured())
    assert tasks.flush(FakeSender, get_settings()) == {"sent": 0, "failed": 0}
    assert FakeSender.sent == []
    with sync_session() as db:
        assert db.scalars(select(OutboundEmail)).one().status == "not_configured"
        assert db.scalars(select(Complaint)).one().channel == "email"


def test_mailbox_jobs_run_from_the_settings_tick() -> None:
    from app_settings.jobs import JOBS

    assert {"mailbox-check", "email-outbox", "sla-risk-scan"} <= set(JOBS)


# ---------------------------------------------------------------- final-review regressions


def test_unknown_charset_and_long_headers_do_not_stall_the_mailbox() -> None:
    odd = build(text=BODY, message_id="<odd@x>").replace(
        b'charset="utf-8"', b'charset="x-unknown-foo"'
    )
    long_name = build(
        text=BODY.replace("tablet", "phone"),
        sender=f"{'Very Long Name ' * 20} <long@example.test>",
        message_id=f"<{'x' * 400}@example.test>",
    )
    after = build(text=BODY.replace("tablet", "laptop"), message_id="<after@x>",
                  sender="Kim <kim@example.test>")  # fmt: skip
    box = FakeMailbox([odd, long_name, after])
    assert tasks.check(lambda s: box, configured()) == {"status": "ok", "processed": 3}
    assert sorted(box.seen) == [b"1", b"2", b"3"]
    with sync_session() as db:
        assert {r.outcome for r in db.scalars(select(InboundEmail))} == {"filed"}


def test_a_message_that_cannot_even_be_recorded_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*_: object, **__: object) -> str:
        raise RuntimeError("processing failed")

    async def also_boom(*_: object, **__: object) -> int:
        raise RuntimeError("database gone")

    monkeypatch.setattr(tasks, "_process_one", boom)
    monkeypatch.setattr(tasks, "_record_failure", also_boom)
    box = FakeMailbox([build(text=BODY)])
    assert tasks.check(lambda s: box, configured())["status"] == "ok"
    assert box.seen == [b"1"]  # given up on, so later messages are not blocked forever


def test_mark_seen_failure_after_filing_keeps_the_complaint_filed() -> None:
    class FlakyBox(FakeMailbox):
        fail_once = True

        def mark_seen(self, uid: bytes) -> None:
            if FlakyBox.fail_once:
                FlakyBox.fail_once = False
                raise OSError("IMAP connection dropped")
            super().mark_seen(uid)

    box = FlakyBox([build(text=BODY)])
    tasks.check(lambda s: box, configured())
    tasks.check(lambda s: box, configured())
    assert box.seen == [b"1"]
    with sync_session() as db:
        record = db.scalars(select(InboundEmail)).one()
        assert record.outcome == "filed"
        kinds = [o.kind for o in db.scalars(select(OutboundEmail))]
        assert kinds == ["acknowledgement"]  # no false "duplicate" notice


def test_storage_failure_after_filing_is_retried_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.core.storage import get_storage

    storage = get_storage()
    real_put = storage.put
    calls = {"n": 0}

    def flaky_put(key: str, data: bytes, content_type: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("storage unavailable")
        real_put(key, data, content_type)

    monkeypatch.setattr(storage, "put", flaky_put)
    analysed: list[object] = []
    from complaint_processing import service

    monkeypatch.setattr(service, "enqueue_analysis", lambda cid, _by=None: analysed.append(cid))
    raw = build(
        text=BODY, attachments=(("photo.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"0" * 8),)
    )
    box = FakeMailbox([raw])
    tasks.check(lambda s: box, configured())
    with sync_session() as db:
        assert db.scalars(select(Complaint)).all() == []  # nothing half-filed
        assert db.scalars(select(InboundEmail)).one().attempts == 1
    tasks.check(lambda s: box, configured())
    with sync_session() as db:
        complaint = db.scalars(select(Complaint)).one()
        assert len(complaint.attachments) == 1
        assert [o.kind for o in db.scalars(select(OutboundEmail))] == ["acknowledgement"]
    assert len(analysed) == 1


def test_short_subject_falls_back_to_the_first_line() -> None:
    box = FakeMailbox([build(text=BODY, subject="Help")])
    tasks.check(lambda s: box, configured())
    with sync_session() as db:
        complaint = db.scalars(select(Complaint)).one()
        assert complaint.title.startswith("My tablet arrived with a cracked screen")
