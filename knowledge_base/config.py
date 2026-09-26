"""Knowledge-base configuration (document categories and precedence), read from YAML."""

from functools import lru_cache

import yaml
from pydantic import BaseModel

from src.core.config import ROOT_DIR

CONFIG_FILE = ROOT_DIR / "config" / "knowledge_base.yaml"


class DocumentType(BaseModel):
    code: str
    name: str
    # Lower number wins when two sources disagree (e.g. policy beats FAQ).
    precedence: int


class KnowledgeBaseConfig(BaseModel):
    document_types: list[DocumentType]

    @property
    def type_codes(self) -> set[str]:
        return {t.code for t in self.document_types}


@lru_cache
def get_kb_config() -> KnowledgeBaseConfig:
    with CONFIG_FILE.open(encoding="utf-8") as handle:
        return KnowledgeBaseConfig.model_validate(yaml.safe_load(handle))
