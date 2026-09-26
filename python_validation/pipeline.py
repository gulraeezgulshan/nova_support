"""Run the Ground-Truth Validation Pipeline for a complaint and apply its decision.

Loads the facts from the database, validates the latest GenAI analysis (or, when the GenAI
pipeline failed, applies the rule matrix on its own), stores a `ValidationRun`, updates the
complaint with the enforced values and opens a manual-review task when a human is needed.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from comparison_engine.labels import expected_labels
from complaint_processing.facts import build_facts
from complaint_rules.matrix import load_specs
from database import audit
from database.models import (
    AnalysisRun,
    Chunk,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    Document,
    DocumentVersion,
    ReviewStatus,
    ReviewTask,
    Rule,
    RunStatus,
    SlaPolicy,
    ValidationRun,
)
from genai_pipeline.vocabulary import load_vocabulary
from knowledge_base.config import get_kb_config
from python_validation.checks import PolicyPassage, ValidationInput, compare, validate
from python_validation.types import Verdict
from schemas.complaint_analysis import ComplaintAnalysis
from src.core.logging import get_logger

log = get_logger(__name__)

OPEN_STATUSES = {ComplaintStatus.NEW, ComplaintStatus.ANALYZED, ComplaintStatus.REOPENED}


def rules_fingerprint(db: Session) -> str:
    rows = db.execute(select(Rule.rule_id, Rule.version, Rule.is_active).order_by(Rule.rule_id))
    return hashlib.sha256(repr(rows.all()).encode()).hexdigest()[:12]


def _passages(db: Session, run: AnalysisRun | None) -> list[PolicyPassage]:
    if run is None or not run.retrieved_policies:
        return []
    codes = [p["chunk_code"] for p in run.retrieved_policies]
    rows = db.execute(
        select(Chunk, DocumentVersion.status, Document.doc_type)
        .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Chunk.chunk_code.in_(codes))
    ).all()
    precedence = {t.code: t.precedence for t in get_kb_config().document_types}
    return [
        PolicyPassage(
            chunk_code=chunk.chunk_code,
            doc_code=chunk.doc_code,
            doc_type=doc_type,
            precedence=precedence.get(doc_type, 99),
            version=chunk.version,
            content=chunk.content,
            status=str(status),
        )
        for chunk, status, doc_type in rows
    ]


def _record_texts(complaint: Complaint, history: list[Complaint]) -> list[str]:
    texts = [f"Customer {complaint.customer.customer_ref}"]
    order = complaint.order
    if order:
        dates = [order.order_date, order.committed_delivery_date, order.delivered_date]
        texts.append(
            f"Order {order.order_ref} {order.transaction_ref or ''} USD {order.amount} "
            + " ".join(f"{d.isoformat()} {d.day} {d.strftime('%B %Y')}" for d in dates if d)
        )
    texts += [f"{c.complaint_ref} {c.created_at.date().isoformat()}" for c in history]
    texts.append(complaint.created_at.date().isoformat())
    return texts


def latest_analysis(db: Session, complaint_id: uuid.UUID) -> AnalysisRun | None:
    return db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.complaint_id == complaint_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )


def build_input(
    db: Session, complaint: Complaint
) -> tuple[ValidationInput, AnalysisRun | None, ComplaintAnalysis | None]:
    """Everything Pipeline 2 needs for one complaint, loaded from the database."""
    run = latest_analysis(db, complaint.id)
    analysis = (
        ComplaintAnalysis.model_validate(run.output)
        if run is not None and run.status == RunStatus.COMPLETED and run.output
        else None
    )
    vocab = load_vocabulary(db)
    history = list(
        db.scalars(
            select(Complaint)
            .where(
                Complaint.customer_id == complaint.customer_id,
                Complaint.id != complaint.id,
                Complaint.created_at <= complaint.created_at,
            )
            .order_by(Complaint.created_at.desc())
            .limit(10)
        )
    )
    sla = {
        s.priority: (s.first_response_minutes / 60, s.resolution_minutes / 60)
        for s in db.scalars(select(SlaPolicy))
    }
    text = "\n".join(
        filter(None, [complaint.title, complaint.description, complaint.requested_resolution])
    )
    inp = ValidationInput(
        complaint_ref=complaint.complaint_ref,
        text=text,
        signals=complaint.signals or {},
        facts=build_facts(complaint, history, complaint.created_at.date()),
        taxonomy=vocab.categories,
        vocab=vocab,
        rules=load_specs(db),
        analysis=analysis,
        passages=_passages(db, run),
        record_texts=_record_texts(complaint, history),
        reference_date=complaint.created_at.date(),
        sla_hours=sla,
    )
    return inp, run, analysis


def run_validation(
    db: Session, complaint_id: uuid.UUID, actor_user_id: uuid.UUID | None = None
) -> ValidationRun:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise ValueError(f"Complaint {complaint_id} not found")
    inp, run, analysis = build_input(db, complaint)
    vocab = inp.vocab
    outcome = validate(inp)
    reasons = list(outcome.review_reasons)
    if run is not None and run.status != RunStatus.COMPLETED:
        reasons.insert(
            0, f"GenAI analysis {run.status}: {run.error or '; '.join(run.validation_errors)}"
        )
    elif run is None:
        reasons.insert(0, "No GenAI analysis has run yet.")
    verdict = Verdict.NEEDS_REVIEW if reasons else outcome.verdict

    validation = ValidationRun(
        complaint_id=complaint.id,
        analysis_run_id=run.id if run else None,
        verdict=verdict,
        score=outcome.score,
        checks=[c.to_dict() for c in outcome.checks],
        python_decision=outcome.python_expected(),
        comparison=compare(outcome, analysis, vocab, expected_labels(complaint.external_ref)),
        final_recommendation=outcome.final,
        corrections=outcome.corrections,
        review_reasons=reasons,
        rules_version=rules_fingerprint(db),
    )
    db.add(validation)
    db.flush()
    _apply(db, complaint, validation, outcome.final, verdict, reasons)
    audit.record_sync(
        db, "complaint.validated", "complaint", complaint.id, actor_user_id=actor_user_id,
        after={"verdict": verdict, "score": outcome.score, "corrections": len(outcome.corrections)},
    )  # fmt: skip
    db.commit()
    log.info("validation.completed", complaint=complaint.complaint_ref, verdict=verdict)
    return validation


def _apply(
    db: Session,
    complaint: Complaint,
    validation: ValidationRun,
    final: dict[str, Any],
    verdict: Verdict,
    reasons: list[str],
) -> None:
    complaint.category_code = final["category"]
    complaint.subcategory_code = final["subcategory"]
    complaint.department_code = final["department"]
    complaint.supporting_departments = final["supporting_departments"]
    complaint.urgency = final["urgency"]
    complaint.priority = final["priority"]
    complaint.escalation_level = final["escalation_level"]
    if final.get("sentiment"):
        complaint.sentiment = final["sentiment"]
    complaint.verification = verdict

    if verdict == Verdict.NEEDS_REVIEW:
        complaint.needs_review = True
        complaint.review_reason = "; ".join(reasons)[:2000]
        open_review_task(db, complaint, validation.id, reasons)
    else:
        complaint.needs_review = False
        complaint.review_reason = None
        if complaint.status in OPEN_STATUSES:
            escalated = final["escalation_level"] >= 1
            target = ComplaintStatus.ESCALATED if escalated else ComplaintStatus.ASSIGNED
            department = final["department"].replace("_", " ").title()
            change_status(
                db, complaint, target,
                f"Your complaint has been escalated to a senior {department} team."
                if escalated else f"Your complaint has been assigned to our {department} team.",
            )  # fmt: skip


def open_review_task(
    db: Session, complaint: Complaint, validation_id: uuid.UUID | None, reasons: list[str]
) -> ReviewTask:
    """Create, or add reasons to, the complaint's open review task (one open task at a time)."""
    task = db.scalar(
        select(ReviewTask).where(
            ReviewTask.complaint_id == complaint.id, ReviewTask.status == ReviewStatus.OPEN
        )
    )
    if task is None:
        task = ReviewTask(complaint_id=complaint.id, reasons=[], status=ReviewStatus.OPEN)
        db.add(task)
        db.add(
            ComplaintEvent(
                complaint_id=complaint.id,
                event_type="review_opened",
                message="Sent for manual review: " + "; ".join(reasons)[:500],
                customer_visible=False,
            )
        )
    task.reasons = list(dict.fromkeys([*reasons, *task.reasons]))
    task.validation_run_id = validation_id or task.validation_run_id
    task.priority = complaint.priority
    return task


def change_status(
    db: Session,
    complaint: Complaint,
    to_status: ComplaintStatus,
    message: str,
    actor_user_id: uuid.UUID | None = None,
) -> None:
    if complaint.status == to_status:
        return
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            event_type="status_changed",
            from_status=complaint.status,
            to_status=to_status,
            message=message,
            actor_user_id=actor_user_id,
            created_at=datetime.now(UTC),
        )
    )
    complaint.status = to_status
