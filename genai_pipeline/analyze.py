"""Run the GenAI pipeline over stored complaints (sequentially, with the configured model).

Usage (repo root):
    uv run python -m genai_pipeline.analyze --limit 10   # unanalysed dataset complaints
    uv run python -m genai_pipeline.analyze --refs CMP-000012 CMP-000040

Needs the selected provider's API key in .env (ANTHROPIC_API_KEY or OPENAI_API_KEY, see
GENAI_PROVIDER). Each complaint costs one or two model calls.
"""

import argparse
import sys
import time
import uuid

from sqlalchemy import select

from database.models import AnalysisRun, Complaint
from database.session import sync_session
from genai_pipeline.pipeline import run_analysis
from genai_pipeline.providers import ProviderUnavailableError, get_provider
from knowledge_base.embeddings import get_embedder
from python_validation.pipeline import run_validation
from src.core.config import get_settings
from src.core.logging import configure_logging


def select_ids(refs: list[str], limit: int, source: str, include_analysed: bool) -> list[str]:
    with sync_session() as db:
        stmt = select(Complaint.id).order_by(Complaint.created_at)
        if refs:
            stmt = stmt.where(Complaint.complaint_ref.in_([r.upper() for r in refs]))
        else:
            stmt = stmt.where(Complaint.source == source)
            if not include_analysed:
                stmt = stmt.where(~Complaint.id.in_(select(AnalysisRun.complaint_id)))
        return [str(i) for i in db.scalars(stmt.limit(limit))]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyse stored complaints with the GenAI pipeline"
    )
    parser.add_argument("--refs", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--source", default="dataset")
    parser.add_argument("--include-analysed", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    if not settings.genai_api_key:
        selected = settings.genai_provider
        print(f"{settings.genai_api_key_name} is not set in .env (GENAI_PROVIDER={selected})")
        return 1
    configure_logging("WARNING", json=False)
    provider, embedder = get_provider(), get_embedder()
    ids = select_ids(args.refs, args.limit, args.source, args.include_analysed)
    print(f"Analysing {len(ids)} complaint(s) with {provider.name}/{provider.model}")
    for complaint_id in ids:
        started = time.monotonic()
        with sync_session() as db:
            try:
                run = run_analysis(
                    db,
                    uuid.UUID(complaint_id),
                    provider=provider,
                    embedder=embedder,
                    settings=settings,
                )
            except ProviderUnavailableError as exc:
                print(f"  provider unavailable: {exc}")
                return 2
            validation = run_validation(db, run.complaint_id)
            complaint = db.get(Complaint, run.complaint_id)
            assert complaint is not None
            print(
                f"  {complaint.complaint_ref} {run.status:>12} {validation.verdict:>12} "
                f"{time.monotonic() - started:5.1f}s attempts={run.attempts} -> "
                f"{complaint.category_code}/{complaint.subcategory_code} "
                f"{complaint.priority} {complaint.department_code}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
