"""Write the OpenAPI schema for the frontend client generator.

Usage (from the repo root): `uv run python -m src.export_openapi`
"""

import json

from src.core.config import ROOT_DIR
from src.main import app

TARGET = ROOT_DIR / "web" / "openapi.json"

if __name__ == "__main__":
    TARGET.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {TARGET.relative_to(ROOT_DIR)}")
