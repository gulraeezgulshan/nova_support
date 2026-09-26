"""Export GenAI pipeline evidence (SRS deliverable 6) from the call log.

    uv run python -m genai_pipeline.evidence

Writes `documentation/evidence/`:

- `generation_config.json`: provider, model, effort, attempts, prompt versions and schema.
- `sample_request.json` / `sample_response.json`: one real, valid call (prompt and answer).
- `invalid_responses.json`: calls whose output failed validation, with the errors found.
- `retry_evidence.json`: runs that needed the repair retry, showing both attempts.
- `runs_summary.json`: counts, token use and latency across all runs.

Everything comes from `llm_calls` / `analysis_runs`, i.e. what the application actually sent
and received. Run it after analysing some complaints with a real API key.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from database.models import AnalysisRun, LlmCall, PromptVersion
from database.session import sync_session
from src.core.config import ROOT_DIR, get_settings

OUT = ROOT_DIR / "documentation" / "evidence"


def _call(call: LlmCall) -> dict[str, Any]:
    return {
        "analysis_run_id": str(call.analysis_run_id),
        "attempt": call.attempt,
        "provider": call.provider,
        "model": call.model,
        "request_id": call.request_id,
        "outcome": call.outcome,
        "errors": call.errors,
        "stop_reason": call.stop_reason,
        "input_tokens": call.input_tokens,
        "output_tokens": call.output_tokens,
        "cache_read_tokens": call.cache_read_tokens,
        "latency_ms": call.latency_ms,
        "created_at": call.created_at.isoformat(),
    }


def _write(name: str, data: Any) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False))
    print(f"  wrote {(OUT / name).relative_to(ROOT_DIR)}")


def export(out: Path = OUT) -> int:
    out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    with sync_session() as db:
        calls = db.scalar(select(func.count()).select_from(LlmCall)) or 0
        if not calls:
            print("No GenAI calls logged yet. Analyse complaints first (make analyze).")
            return 1
        prompts = db.scalars(select(PromptVersion).order_by(PromptVersion.created_at)).all()
        _write(
            "generation_config.json",
            {
                "provider": settings.genai_provider,
                "model": settings.genai_model,
                "effort": settings.genai_effort,
                "max_attempts": settings.genai_max_attempts,
                "timeout_seconds": settings.genai_timeout_seconds,
                "structured_output": "JSON schema complaint_analysis.v1, generated from the live "
                "taxonomy (schema fingerprints are stored per run in analysis_runs.schema_version)",
                "schema_versions": sorted(
                    {v for v in db.scalars(select(AnalysisRun.schema_version)) if v}
                ),
                "prompt_versions": [
                    {
                        "name": p.name,
                        "version": p.version,
                        "sha256": p.sha256,
                        "first_used": p.created_at.isoformat(),
                    }
                    for p in prompts
                ],
            },
        )

        valid = db.scalars(
            select(LlmCall).where(LlmCall.outcome == "valid").order_by(LlmCall.id).limit(1)
        ).first()
        if valid is not None:
            _write("sample_request.json", {**_call(valid), "request": valid.request})
            response = json.loads(valid.response_text) if valid.response_text else None
            _write("sample_response.json", {**_call(valid), "response": response})

        invalid = db.scalars(
            select(LlmCall).where(LlmCall.outcome != "valid").order_by(LlmCall.id).limit(20)
        ).all()
        _write(
            "invalid_responses.json",
            [{**_call(c), "response_text": c.response_text} for c in invalid],
        )

        retried = db.scalars(
            select(AnalysisRun).where(AnalysisRun.attempts > 1).order_by(AnalysisRun.created_at)
        ).all()[:10]
        _write(
            "retry_evidence.json",
            [
                {
                    "analysis_run_id": str(run.id),
                    "final_status": run.status,
                    "attempts": [
                        {**_call(c), "response_text": c.response_text}
                        for c in db.scalars(
                            select(LlmCall)
                            .where(LlmCall.analysis_run_id == run.id)
                            .order_by(LlmCall.attempt)
                        )
                    ],
                }
                for run in retried
            ],
        )

        runs = db.scalars(select(AnalysisRun)).all()
        latencies = [r.latency_ms / 1000 for r in runs if r.latency_ms]
        _write(
            "runs_summary.json",
            {
                "runs": len(runs),
                "calls": calls,
                "run_status": dict(Counter(str(r.status) for r in runs)),
                "runs_needing_retry": sum(r.attempts > 1 for r in runs),
                "input_tokens": sum(r.input_tokens for r in runs),
                "output_tokens": sum(r.output_tokens for r in runs),
                "model_latency_seconds": {
                    "median": round(statistics.median(latencies), 2) if latencies else None,
                    "max": round(max(latencies), 2) if latencies else None,
                },
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(export())
