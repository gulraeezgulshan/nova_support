"""Bulk-import knowledge-base documents from a folder (sample data or a hidden evaluation pack).

Each file goes through exactly the same validation, versioning and ingestion as an upload
in the web UI; ingestion runs inline, so no Celery worker is needed.

Usage (repo root):
    uv run python -m knowledge_base.import_documents sample_documents/generated
    uv run python -m knowledge_base.import_documents hidden_test_ready/documents --no-activate
"""

import argparse
import asyncio
import sys
from pathlib import Path

from database.models import IngestStatus
from database.session import async_session_factory, sync_session
from document_processing.validation import MEDIA_TYPES, DocumentValidationError
from knowledge_base.embeddings import get_embedder
from knowledge_base.ingestion import ingest_version
from knowledge_base.service import DuplicateDocumentError, upload_document
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.storage import get_storage


async def import_file(path: Path, activate: bool) -> tuple[str, str]:
    settings, storage = get_settings(), get_storage()
    async with async_session_factory()() as db:
        try:
            version = await upload_document(
                db,
                filename=path.name,
                data=await asyncio.to_thread(path.read_bytes),
                form={},
                activate=activate,
                actor=None,
                storage=storage,
                settings=settings,
                enqueue=False,
            )
        except DuplicateDocumentError as exc:
            return "skipped", str(exc)
        except DocumentValidationError as exc:
            return "rejected", "; ".join(exc.issues)

    with sync_session() as sync_db:
        result = ingest_version(
            sync_db, version.id, storage=storage, embedder=get_embedder(), settings=settings
        )
        if result.ingest_status == IngestStatus.FAILED:
            return "failed", result.ingest_error or "unknown error"
        return "imported", f"v{result.version} {result.status}, {result.chunk_count} chunks"


def find_documents(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lstrip(".").lower() in MEDIA_TYPES)


async def main(files: list[Path], activate: bool) -> int:
    failures = 0
    for path in files:
        outcome, detail = await import_file(path, activate)
        failures += outcome in ("rejected", "failed")
        print(f"{outcome:>9}  {path.name}  -  {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--no-activate", action="store_true", help="import as draft versions")
    args = parser.parse_args()
    configure_logging("WARNING", json=False)
    documents = find_documents(args.folder)
    if not documents:
        sys.exit(f"No PDF/DOCX/TXT/MD files in {args.folder}")
    sys.exit(asyncio.run(main(documents, activate=not args.no_activate)))
