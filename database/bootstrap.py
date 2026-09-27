"""One-command setup of a fresh database (local or deployed).

    uv run python -m database.bootstrap                  # taxonomy, rules, documents, dataset
    uv run python -m database.bootstrap --no-dataset     # everything except sample complaints
    uv run python -m database.bootstrap --with-holdout   # also the hold-out evaluation pack

Run `alembic upgrade head` first (the deployment does this before every release). Every
step is idempotent: running it again adds only what is missing.
"""

import argparse
import asyncio
import sys

from database.seed import load_taxonomy, seed_rules, seed_taxonomy
from database.session import sync_session
from knowledge_base.import_documents import find_documents
from knowledge_base.import_documents import main as import_documents
from sample_complaints.load_dataset import HERE as DATASET_DIR
from sample_complaints.load_dataset import load
from src.core.config import ROOT_DIR
from src.core.logging import configure_logging
from storefront.catalogue import sync_catalogue

DOCUMENTS = ROOT_DIR / "sample_documents" / "generated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--no-dataset", action="store_true")
    parser.add_argument("--with-holdout", action="store_true")
    args = parser.parse_args()
    configure_logging("WARNING", json=False)

    with sync_session() as db:
        counts = seed_taxonomy(db, load_taxonomy())
        rules = seed_rules(db)
        products = sync_catalogue(db)
    print(f"Taxonomy: {counts}; rules: {rules}; products: {products}")

    # Archived versions first, so the current versions supersede them.
    for folder in (DOCUMENTS / "archive", DOCUMENTS):
        print(f"Documents in {folder.relative_to(ROOT_DIR)} (already imported ones are rejected):")
        asyncio.run(import_documents(find_documents(folder), activate=True))

    if not args.no_dataset:
        outcomes = asyncio.run(load(DATASET_DIR))
        print(f"Dataset: {dict(outcomes)}")
    if args.with_holdout:
        outcomes = asyncio.run(load(ROOT_DIR / "hidden_test_ready" / "holdout", "evaluation"))
        print(f"Hold-out pack: {dict(outcomes)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
