"""Expected labels for dataset and evaluation-pack complaints (matched by `external_ref`).

Labels come from `sample_complaints/complaints.jsonl` and, when present, any
`hidden_test_ready/**/*.jsonl` evaluation file with the same record format.
"""

import json
from functools import lru_cache
from typing import Any

from src.core.config import ROOT_DIR

LABEL_FILES = [ROOT_DIR / "sample_complaints" / "complaints.jsonl"]
LABEL_GLOB = (ROOT_DIR / "hidden_test_ready", "**/*.jsonl")


@lru_cache
def _labels() -> dict[str, dict[str, Any]]:
    files = list(LABEL_FILES) + sorted(LABEL_GLOB[0].glob(LABEL_GLOB[1]))
    labels: dict[str, dict[str, Any]] = {}
    for path in files:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                if "expected" in record:
                    labels[record["dataset_id"]] = record["expected"]
    return labels


def expected_labels(external_ref: str | None) -> dict[str, Any] | None:
    return _labels().get(external_ref) if external_ref else None
