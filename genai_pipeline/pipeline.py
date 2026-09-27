"""GenAI Complaint Intelligence Pipeline (Pipeline 1).

For one complaint: gather context (complaint, customer, order, history), retrieve active
policy passages, render the versioned prompt, call the model with a JSON-schema constraint,
validate the output in Python, and retry once with the validation errors if it is invalid.

Invalid output after the allowed attempts is never used: the run ends as NEEDS_REVIEW and
the complaint is flagged for manual review (SRS Step 47). Every model call is stored with
its request, raw response, outcome and token usage.
"""

import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from complaint_processing.attachments import describe
from complaint_processing.facts import build_facts
from database.models import (
    AnalysisRun,
    Complaint,
    ComplaintEvent,
    ComplaintStatus,
    LlmCall,
    RunStatus,
)
from genai_pipeline.output_schema import build_json_schema, schema_version
from genai_pipeline.prompts import load_template, register
from genai_pipeline.providers import (
    LLMProvider,
    LLMRequest,
    ProviderRequestError,
    ProviderUnavailableError,
)
from genai_pipeline.validation import parse_and_validate
from genai_pipeline.vocabulary import Vocabulary, load_vocabulary
from knowledge_base.embeddings import Embedder
from knowledge_base.retrieval import RetrievedChunk, search_chunks_sync
from schemas.complaint_analysis import SCHEMA_NAME, ComplaintAnalysis
from src.core.config import Settings
from src.core.domain import analysis_config, organization
from src.core.logging import get_logger

log = get_logger(__name__)

PROMPT_NAME = "complaint_analysis"
HISTORY_LIMIT = 10


def retrieval_query(complaint: Complaint) -> str:
    parts = [complaint.title, complaint.product_service or "", complaint.description]
    return " ".join(parts)[:1500]


def run_analysis(
    db: Session,
    complaint_id: uuid.UUID,
    *,
    provider: LLMProvider,
    embedder: Embedder,
    settings: Settings,
    triggered_by: uuid.UUID | None = None,
) -> AnalysisRun:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise ValueError(f"Complaint {complaint_id} not found")

    template = load_template(PROMPT_NAME)
    prompt_version = register(db, template)
    vocab = load_vocabulary(db)
    schema = build_json_schema(vocab)
    history = list(
        db.scalars(
            select(Complaint)
            .where(
                Complaint.customer_id == complaint.customer_id,
                Complaint.id != complaint.id,
                Complaint.created_at <= complaint.created_at,
            )
            .order_by(Complaint.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
    )
    policies = search_chunks_sync(
        db, retrieval_query(complaint), embedder, settings.retrieval_limit
    )
    retrieved = {p.chunk_code: p.doc_code for p in policies}

    run = AnalysisRun(
        complaint_id=complaint.id,
        status=RunStatus.RUNNING,
        triggered_by_id=triggered_by,
        prompt_version_id=prompt_version.id,
        prompt_name=template.name,
        prompt_version=template.version,
        provider=provider.name,
        model=provider.model,
        schema_version=f"{SCHEMA_NAME}+{schema_version(schema)}",
        retrieved_policies=[_policy_record(p) for p in policies],
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()

    context = {
        "organization": organization(),
        "vocab": vocab,
        "complaint": complaint,
        "customer": complaint.customer,
        "order": complaint.order,
        "facts": build_facts(complaint, history, complaint.created_at.date()),
        "history": history,
        "policies": policies,
        "supporting_documents": describe([a.media_type for a in complaint.attachments]),
    }
    errors: list[str] = []
    analysis: ComplaintAnalysis | None = None
    try:
        for attempt in range(1, settings.genai_max_attempts + 1):
            system, user = template.render(**context, previous_errors=errors)
            request = LLMRequest(
                system=system,
                user=user,
                json_schema=schema,
                max_tokens=int(template.parameters.get("max_tokens", 8000)),
            )
            analysis, errors = _attempt(db, run, provider, request, attempt, vocab, retrieved)
            if analysis is not None and not errors:
                break
    except ProviderUnavailableError as exc:
        _finish(db, run, complaint, RunStatus.FAILED, error=str(exc))
        raise
    except ProviderRequestError as exc:  # e.g. invalid API key: retrying cannot help
        _finish(db, run, complaint, RunStatus.FAILED, error=str(exc))
        return run

    if analysis is not None and not errors:
        _finish(db, run, complaint, RunStatus.COMPLETED, analysis=analysis)
    else:
        _finish(db, run, complaint, RunStatus.NEEDS_REVIEW, errors=errors)
    return run


def _attempt(
    db: Session,
    run: AnalysisRun,
    provider: LLMProvider,
    request: LLMRequest,
    attempt: int,
    vocab: Vocabulary,
    retrieved: dict[str, str],
) -> tuple[ComplaintAnalysis | None, list[str]]:
    call = LlmCall(
        analysis_run_id=run.id,
        attempt=attempt,
        provider=provider.name,
        model=provider.model,
        request={"system": request.system, "user": request.user, "max_tokens": request.max_tokens},
        outcome="error",
    )
    run.attempts = attempt
    try:
        response = provider.complete(request)
    except ProviderUnavailableError as exc:
        call.errors = [str(exc)]
        db.add(call)
        db.commit()
        raise
    except ProviderRequestError as exc:
        call.errors = [str(exc)]
        db.add(call)
        db.commit()
        raise

    call.model = response.model
    call.request_id = response.request_id
    call.response_text = response.text
    call.stop_reason = response.stop_reason
    call.input_tokens = response.input_tokens
    call.output_tokens = response.output_tokens
    call.cache_read_tokens = response.cache_read_tokens
    call.latency_ms = response.latency_ms
    call.request = {**call.request, **response.details}
    run.input_tokens += response.input_tokens
    run.output_tokens += response.output_tokens
    run.latency_ms += response.latency_ms

    if response.stop_reason == "refusal":
        errors = ["The model declined to answer (refusal)."]
        analysis = None
    elif response.stop_reason == "max_tokens":
        errors = ["The response was cut off at the token limit (incomplete JSON)."]
        analysis = None
    else:
        analysis, errors = parse_and_validate(response.text, vocab, retrieved)
    call.outcome = "valid" if analysis is not None and not errors else "invalid"
    call.errors = errors
    db.add(call)
    db.commit()
    log.info(
        "analysis.attempt",
        run_id=str(run.id),
        attempt=attempt,
        outcome=call.outcome,
        errors=len(errors),
        latency_ms=response.latency_ms,
    )
    return analysis, errors


def _finish(
    db: Session,
    run: AnalysisRun,
    complaint: Complaint,
    status: RunStatus,
    *,
    analysis: ComplaintAnalysis | None = None,
    errors: list[str] | None = None,
    error: str | None = None,
) -> None:
    run.status = status
    run.completed_at = datetime.now(UTC)
    run.validation_errors = errors or []
    run.error = error
    if analysis is not None:
        run.output = analysis.model_dump(mode="json")
        levels = {lvl.code: lvl.level for lvl in analysis_config().escalation_levels}
        complaint.category_code = analysis.primary_issue.category
        complaint.subcategory_code = analysis.primary_issue.subcategory
        complaint.department_code = analysis.department
        complaint.urgency = analysis.urgency
        complaint.priority = analysis.priority
        complaint.sentiment = analysis.sentiment
        complaint.escalation_level = levels.get(analysis.escalation.level, 0)
        if complaint.status in (ComplaintStatus.NEW, ComplaintStatus.REOPENED):
            _event(db, complaint, ComplaintStatus.ANALYZED, "Your complaint is being reviewed.")
        complaint.needs_review = False
        complaint.review_reason = None
    else:
        complaint.needs_review = True
        complaint.review_reason = (
            f"Automatic analysis failed: {error}"
            if error
            else f"GenAI output invalid after {run.attempts} attempt(s): {'; '.join(errors or [])}"
        )[:2000]
        db.add(
            ComplaintEvent(
                complaint_id=complaint.id,
                event_type="analysis_needs_review",
                message="Automatic analysis could not be completed; sent for manual review.",
                customer_visible=False,
            )
        )
    db.commit()


def _event(db: Session, complaint: Complaint, to_status: ComplaintStatus, message: str) -> None:
    db.add(
        ComplaintEvent(
            complaint_id=complaint.id,
            event_type="status_changed",
            from_status=complaint.status,
            to_status=to_status,
            message=message,
        )
    )
    complaint.status = to_status


def _policy_record(p: RetrievedChunk) -> dict[str, object]:
    record = asdict(p)
    record.pop("content")
    return record
