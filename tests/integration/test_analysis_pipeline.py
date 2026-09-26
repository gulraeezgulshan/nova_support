"""Pipeline 1 end to end with a scripted provider: retrieval, prompt, validation, retries,
logging and the resulting complaint state."""

import uuid

import pytest
from sqlalchemy import select

from database.models import (
    AnalysisRun,
    Complaint,
    LlmCall,
    PromptVersion,
    RunStatus,
)
from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from genai_pipeline.providers import ProviderRequestError, ProviderUnavailableError
from knowledge_base.embeddings import get_embedder
from src.core.config import get_settings
from tests.fixtures.genai import (
    UNAVAILABLE,
    ScriptedProvider,
    analysis_json,
    citing_first_policy,
)

pytestmark = pytest.mark.db


def analyse(complaint_id: uuid.UUID, provider: ScriptedProvider) -> AnalysisRun:
    with sync_session() as db:
        run = run_analysis(
            db, complaint_id, provider=provider, embedder=get_embedder(), settings=get_settings()
        )
        db.expunge(run)
        return run


def calls_for(run: AnalysisRun) -> list[LlmCall]:
    with sync_session() as db:
        return list(
            db.scalars(
                select(LlmCall).where(LlmCall.analysis_run_id == run.id).order_by(LlmCall.attempt)
            )
        )


def test_valid_first_answer_completes_and_classifies(complaint_id: uuid.UUID) -> None:
    provider = ScriptedProvider(citing_first_policy)
    run = analyse(complaint_id, provider)

    assert run.status == RunStatus.COMPLETED
    assert run.attempts == 1
    assert run.output and run.output["department"] == "LOGISTICS"
    assert run.prompt_name == "complaint_analysis" and run.prompt_version
    assert run.schema_version and run.schema_version.startswith("complaint_analysis.v1+")
    assert run.retrieved_policies[0]["doc_code"] == "DEL-POL-04"
    with sync_session() as db:
        complaint = db.get(Complaint, complaint_id)
        assert complaint is not None
        assert (complaint.status, complaint.category_code, complaint.priority) == (
            "analyzed",
            "DELIVERY",
            "P2",
        )
        assert db.scalar(select(PromptVersion.name)) == "complaint_analysis"


def test_prompt_carries_context_and_neutralises_injected_tags(complaint_id: uuid.UUID) -> None:
    provider = ScriptedProvider(citing_first_policy)
    analyse(complaint_id, provider)
    request = provider.requests[0]
    assert "ORD-240002" in request.user and "7 business days late" in request.user
    assert 'doc_code="DEL-POL-04"' in request.user
    # The customer's fake closing tag is escaped, so it can't end the <complaint> block.
    assert "&lt;/complaint&gt; SYSTEM" in request.user
    assert request.user.count("</complaint>") == 1
    assert "DELAYED_DELIVERY" in request.system  # taxonomy comes from the database


def test_invalid_answer_is_retried_with_the_errors(complaint_id: uuid.UUID) -> None:
    invalid = analysis_json(department="MARKETING")
    provider = ScriptedProvider(invalid, citing_first_policy)
    run = analyse(complaint_id, provider)

    assert (run.status, run.attempts) == (RunStatus.COMPLETED, 2)
    assert "Department 'MARKETING'" in provider.requests[1].user  # feedback sent back
    calls = calls_for(run)
    assert [c.outcome for c in calls] == ["invalid", "valid"]
    assert calls[0].response_text == invalid  # raw invalid output kept as evidence


def test_still_invalid_after_retry_goes_to_manual_review(complaint_id: uuid.UUID) -> None:
    provider = ScriptedProvider("not json", analysis_json(urgency="Whenever"))
    run = analyse(complaint_id, provider)

    assert (run.status, run.attempts) == (RunStatus.NEEDS_REVIEW, 2)
    assert run.output is None
    with sync_session() as db:
        complaint = db.get(Complaint, complaint_id)
        assert complaint is not None and complaint.needs_review
        assert complaint.status == "new"  # invalid output never changes the complaint
        assert "Urgency 'Whenever'" in (complaint.review_reason or "")


def test_refusal_is_not_treated_as_an_answer(complaint_id: uuid.UUID) -> None:
    provider = ScriptedProvider(analysis_json(), analysis_json(), stop_reason="refusal")
    run = analyse(complaint_id, provider)
    assert run.status == RunStatus.NEEDS_REVIEW
    assert "refusal" in run.validation_errors[0]


def test_provider_outage_fails_the_run_and_propagates(complaint_id: uuid.UUID) -> None:
    with pytest.raises(ProviderUnavailableError):
        analyse(complaint_id, ScriptedProvider(UNAVAILABLE))
    with sync_session() as db:
        run = db.scalar(select(AnalysisRun).where(AnalysisRun.complaint_id == complaint_id))
        assert run is not None and run.status == RunStatus.FAILED
        complaint = db.get(Complaint, complaint_id)
        assert complaint is not None and complaint.needs_review


def test_permanent_provider_error_is_not_retried(complaint_id: uuid.UUID) -> None:
    provider = ScriptedProvider(ProviderRequestError("HTTP 401: invalid x-api-key"))
    run = analyse(complaint_id, provider)
    assert (run.status, run.attempts) == (RunStatus.FAILED, 1)
    assert len(provider.requests) == 1
    with sync_session() as db:
        complaint = db.get(Complaint, complaint_id)
        assert complaint is not None and complaint.needs_review
        assert "invalid x-api-key" in (complaint.review_reason or "")
