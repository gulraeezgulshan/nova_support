"""Knowledge-base document categories and their precedence, from the Settings page.

The defaults ship in config/knowledge_base.yaml; administrators change them under
Settings → Knowledge base.
"""

from pydantic import BaseModel

import app_settings


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


def get_kb_config() -> KnowledgeBaseConfig:
    types = app_settings.runtime().knowledge_base.document_types
    return KnowledgeBaseConfig(document_types=[DocumentType(**t.model_dump()) for t in types])
