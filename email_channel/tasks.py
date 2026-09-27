"""Scheduled mailbox check (every minute) and outbox flush (every 30 s), run by Celery Beat.

`check` and `flush` take their IMAP/SMTP factories as arguments so tests use fakes.
"""

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy import or_, select, text

from database.models import InboundEmail, MailboxState, OutboundEmail
from database.session import get_sync_engine, sync_session, task_session
from email_channel.inbound import new_record, process_email
from email_channel.parsing import ParsedEmail, parse_email
from email_channel.transport import ImapMailbox, Mailbox, Sender, SmtpSender
from src.core.config import Settings, get_settings
from src.core.logging import get_logger
from src.core.storage import get_storage
from src.worker import celery_app

log = get_logger(__name__)
LOCK_KEY = 7_302_001  # PostgreSQL advisory lock id: one mailbox check at a time
BATCH = 25
MAX_ATTEMPTS = 3


async def _process_one(raw: bytes, own: str | None) -> str:
    async with task_session() as db:
        record = await process_email(
            db, parse_email(raw), via="imap", own_address=own, storage=get_storage()
        )
        return record.outcome


async def _record_failure(raw: bytes, error: str) -> int:
    """Count a failed attempt on the message; returns the number of attempts so far.

    A message that was already handled (e.g. filed, then marking it read failed) is never
    downgraded to failed: returning MAX_ATTEMPTS just lets the caller mark it read.
    """
    try:
        parsed = parse_email(raw)
    except Exception:  # unreadable: identify it by its bytes
        digest = hashlib.sha256(raw).hexdigest()[:32]
        parsed = ParsedEmail(f"<unparsed-{digest}@supportnova.local>", "", None, "", "")
    async with task_session() as db:
        record = await db.scalar(
            select(InboundEmail).where(InboundEmail.message_id == parsed.message_id[:300])
        )
        if record is not None and record.outcome != "failed":
            return MAX_ATTEMPTS
        if record is None:
            record = new_record(parsed, "imap")
            db.add(record)
        record.attempts += 1
        record.outcome, record.reason = "failed", error[:2000]
        await db.commit()
        return record.attempts


def _save_state(error: str | None) -> None:
    with sync_session() as db:
        state = db.get(MailboxState, 1) or MailboxState(id=1)
        state.last_check_at, state.last_error = datetime.now(UTC), error
        db.add(state)
        db.commit()


def _mark_seen(box: Mailbox, uid: bytes) -> str | None:
    """Mark read; a failure is only reported (the message is already handled, and handling
    the same Message-ID again is a no-op)."""
    try:
        box.mark_seen(uid)
    except Exception as exc:
        log.warning("mailbox.mark_seen_failed", error=str(exc))
        return f"Could not mark a message as read: {exc}"
    return None


def _read(box: Mailbox, own: str | None) -> tuple[int, str | None]:
    processed, last_error = 0, None
    for uid, raw in box.unseen(BATCH):
        processed += 1
        try:
            asyncio.run(_process_one(raw, own))
        except Exception as exc:  # logged and retried next run; given up after 3 tries
            last_error = f"{type(exc).__name__}: {exc}"
            log.error("mailbox.message_failed", error=last_error)
            try:
                attempts = asyncio.run(_record_failure(raw, last_error))
            except Exception as record_exc:  # cannot even record it: skip, never stall
                log.error("mailbox.failure_not_recorded", error=str(record_exc))
                attempts = MAX_ATTEMPTS
            if attempts >= MAX_ATTEMPTS:
                last_error = _mark_seen(box, uid) or last_error
            continue
        last_error = _mark_seen(box, uid) or last_error
    return processed, last_error


def check(
    mailbox_factory: Callable[[Settings], Mailbox] = ImapMailbox,
    settings: Settings | None = None,
) -> dict[str, int | str]:
    """Read up to 25 unseen messages and process each one."""
    settings = settings or get_settings()
    if not settings.mailbox_configured:
        return {"status": "not_configured"}
    with get_sync_engine().connect() as conn:
        if not conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": LOCK_KEY}).scalar():
            return {"status": "locked"}
        try:
            try:
                box = mailbox_factory(settings)
            except Exception as exc:  # connection or login: recorded, retried next run
                log.warning("mailbox.connect_failed", error=str(exc))
                _save_state(f"Could not connect to the mailbox: {exc}")
                return {"status": "error"}
            try:
                processed, last_error = _read(box, settings.mail_username)
            finally:
                box.close()
            _save_state(last_error)
            return {"status": "ok", "processed": processed}
        finally:
            conn.execute(text("select pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
            conn.commit()


def build_message(email: OutboundEmail, settings: Settings) -> EmailMessage:
    message = EmailMessage()
    message["From"] = formataddr((settings.mail_from_name, settings.mail_username or ""))
    message["To"] = email.to_address
    message["Subject"] = email.subject
    message["Message-ID"] = email.message_id
    if email.in_reply_to:
        message["In-Reply-To"] = email.in_reply_to
        message["References"] = email.references or email.in_reply_to
    # Automatic notices say so, so other auto-responders don't answer them (no mail loops).
    message["Auto-Submitted"] = "no" if email.kind == "reply" else "auto-replied"
    message.set_content(email.body)
    return message


def flush(
    sender_factory: Callable[[Settings], Sender] = SmtpSender,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Send queued e-mails that are due; failures are retried with growing delays."""
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    sent = failed = 0
    with sync_session() as db:
        due = db.scalars(
            select(OutboundEmail)
            .where(
                OutboundEmail.status == "queued",
                or_(OutboundEmail.next_attempt_at.is_(None), OutboundEmail.next_attempt_at <= now),
            )
            .order_by(OutboundEmail.created_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        if not due:
            return {"sent": 0, "failed": 0}
        if not settings.mailbox_configured:
            for email in due:
                email.status = "not_configured"
            db.commit()
            return {"sent": 0, "failed": 0}
        sender = sender_factory(settings)
        for email in due:
            try:
                sender.send(build_message(email, settings))
                email.status, email.sent_at, email.error = "sent", now, None
                sent += 1
            except Exception as exc:  # recorded on the e-mail and retried later
                email.attempts += 1
                email.error = f"{type(exc).__name__}: {exc}"[:2000]
                if email.attempts >= MAX_ATTEMPTS:
                    email.status = "failed"
                else:
                    email.next_attempt_at = now + timedelta(minutes=2**email.attempts)
                failed += 1
        db.commit()
    return {"sent": sent, "failed": failed}


@celery_app.task(name="email_channel.tasks.check_mailbox")  # type: ignore[untyped-decorator]
def check_mailbox() -> dict[str, int | str]:
    return check()


@celery_app.task(name="email_channel.tasks.flush_outbox")  # type: ignore[untyped-decorator]
def flush_outbox() -> dict[str, int]:
    return flush()
