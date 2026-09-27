"""Celery application: document ingestion, complaint analysis and validation, and the
periodic SLA risk scan, mailbox check and e-mail outbox (Celery Beat)."""

from celery import Celery

from src.core.config import ROOT_DIR, get_settings
from src.core.domain import analytics_config
from src.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, json=settings.environment == "production")

celery_app = Celery(
    "supportnova",
    broker=settings.redis_url,
    include=[
        "knowledge_base.tasks",
        "complaint_processing.tasks",
        "email_channel.tasks",
        "bulk_import.tasks",
    ],
)
celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,  # a crashed worker's job is redelivered, not lost
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # ingestion is CPU-heavy; take one job at a time
    task_default_queue="default",
    task_routes={
        "knowledge_base.tasks.*": {"queue": "ingest"},
        "complaint_processing.tasks.*": {"queue": "analysis"},
        "email_channel.tasks.*": {"queue": "default"},
        "bulk_import.tasks.*": {"queue": "default"},
    },
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    beat_schedule={
        "sla-risk-scan": {
            "task": "complaint_processing.tasks.scan_sla",
            "schedule": 60.0 * analytics_config()["sla"]["scan_interval_minutes"],
        },
        # E-mail complaints: read the support mailbox, then send queued e-mails.
        "mailbox-check": {"task": "email_channel.tasks.check_mailbox", "schedule": 60.0},
        "email-outbox": {"task": "email_channel.tasks.flush_outbox", "schedule": 30.0},
    },
    beat_schedule_filename=str(ROOT_DIR / ".data" / "celerybeat-schedule"),
)
