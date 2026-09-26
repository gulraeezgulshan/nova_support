"""Celery application (background jobs: document ingestion now; batch analysis,
SLA scans and report exports in later phases)."""

from celery import Celery

from src.core.config import get_settings
from src.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level, json=settings.environment == "production")

celery_app = Celery("supportnova", broker=settings.redis_url, include=["knowledge_base.tasks"])
celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,  # a crashed worker's job is redelivered, not lost
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # ingestion is CPU-heavy; take one job at a time
    task_default_queue="default",
    task_routes={"knowledge_base.tasks.*": {"queue": "ingest"}},
    broker_connection_retry_on_startup=True,
    timezone="UTC",
)
