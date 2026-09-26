"""Central, versioned prompt templates (SRS Steps 48-49).

Templates live in `prompt_templates/*.yaml` (never inline in code). Each is registered in
the `prompt_versions` table by content hash, so every analysis run can point at the exact
prompt text that produced it.
"""

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import PromptVersion
from src.core.config import ROOT_DIR

TEMPLATE_DIR = ROOT_DIR / "prompt_templates"


def untrusted(value: object) -> str:
    """Neutralise markup in untrusted text so it cannot close or open our XML-style tags."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_ENV = Environment(undefined=StrictUndefined, autoescape=False, trim_blocks=False)  # noqa: S701 - plain-text prompts, untrusted values escaped explicitly
_ENV.filters["untrusted"] = untrusted


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    system: str
    user: str
    parameters: dict[str, Any]
    raw: dict[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.raw, sort_keys=True).encode()).hexdigest()

    def render(self, **context: Any) -> tuple[str, str]:
        system = _ENV.from_string(self.system).render(**context).strip()
        user = _ENV.from_string(self.user).render(**context).strip()
        return system, user


@lru_cache
def load_template(name: str) -> PromptTemplate:
    with (TEMPLATE_DIR / f"{name}.yaml").open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return PromptTemplate(
        name=raw["name"],
        version=str(raw["version"]),
        system=raw["system"],
        user=raw["user"],
        parameters=raw.get("parameters", {}),
        raw=raw,
    )


def register(db: Session, template: PromptTemplate) -> PromptVersion:
    """Return the stored version for this exact template text, creating it if new."""
    existing = db.scalar(select(PromptVersion).where(PromptVersion.sha256 == template.sha256))
    if existing is not None:
        return existing
    version = PromptVersion(
        name=template.name, version=template.version, sha256=template.sha256, template=template.raw
    )
    db.add(version)
    db.flush()
    return version
