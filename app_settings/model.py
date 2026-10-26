"""Settings administrators change at run time (the staff Settings page)."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app_settings.access import AccessSettings, default_access

Provider = Literal["openai", "anthropic"]
Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
LogoTarget = Literal["shop", "console"]

SUGGESTED_MODELS: dict[str, list[str]] = {
    "openai": ["gpt-5-mini", "gpt-5", "gpt-5-nano"],
    "anthropic": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _one_line(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("must be a single line of text")
    return value.strip()


def _email(value: str) -> str:
    if not _EMAIL.match(value):
        raise ValueError("must be an e-mail address")
    return value


Line = Annotated[str, AfterValidator(_one_line)]


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailSettings(_Group):
    mailbox_check_seconds: int = Field(ge=60, le=3600)
    outbox_flush_seconds: int = Field(ge=15, le=600)
    from_name: Annotated[Line, Field(min_length=1, max_length=80)]
    auto_replies: bool


class AiSettings(_Group):
    provider: Provider
    model: Annotated[Line, Field(min_length=1, max_length=100)]
    effort: Effort
    retrieval_limit: int = Field(ge=3, le=20)
    auto_analysis: bool
    timeout_seconds: float = Field(ge=10, le=300)
    max_attempts: int = Field(ge=1, le=3)  # first call + repair retries
    openai_reasoning: bool

    @model_validator(mode="after")
    def _model_matches_provider(self) -> "AiSettings":
        other = "anthropic" if self.provider == "openai" else "openai"
        if self.model in SUGGESTED_MODELS[other]:
            label = "an Anthropic" if other == "anthropic" else "an OpenAI"
            raise ValueError(f"{self.model} is {label} model; choose one for {self.provider}")
        return self


class DocumentTypeSetting(_Group):
    """A knowledge-base document category; lower precedence wins when sources disagree."""

    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,39}$")]
    name: Annotated[Line, Field(min_length=3, max_length=60)]
    precedence: int = Field(ge=1, le=9)


class KnowledgeBaseSettings(_Group):
    chunk_max_tokens: int = Field(ge=100, le=480)  # the embedding model reads at most 512
    chunk_overlap_tokens: int = Field(ge=0)
    max_upload_mb: int = Field(ge=1, le=50)
    retrieval_candidates: int = Field(ge=5, le=100)  # per ranker, before fusion
    rrf_k: int = Field(ge=1, le=200)  # Reciprocal Rank Fusion constant
    document_types: list[DocumentTypeSetting] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _consistent(self) -> "KnowledgeBaseSettings":
        if self.chunk_overlap_tokens > self.chunk_max_tokens - 50:
            raise ValueError(
                f"overlap must be at most {self.chunk_max_tokens - 50} tokens (chunk size minus 50)"
            )
        codes = [t.code for t in self.document_types]
        duplicates = sorted({c for c in codes if codes.count(c) > 1})
        if duplicates:
            raise ValueError(f"document type codes must be unique: {', '.join(duplicates)}")
        return self


class OperationsSettings(_Group):
    sla_scan_minutes: int = Field(ge=1, le=60)
    verified_min_score: int = Field(ge=50, le=100)
    always_review_escalation_level: int = Field(ge=1, le=5)


class BrandingText(_Group):
    shop_name: Annotated[Line, Field(min_length=1, max_length=60)]
    shop_tagline: Annotated[Line, Field(max_length=140)]
    console_name: Annotated[Line, Field(min_length=1, max_length=40)]
    support_email: Annotated[Line, Field(max_length=120), AfterValidator(_email)]
    phone: Annotated[Line, Field(min_length=1, max_length=40)]
    address: Annotated[Line, Field(min_length=1, max_length=200)]
    hours: Annotated[Line, Field(min_length=1, max_length=100)]


class BrandingSettings(BrandingText):
    shop_logo_key: str | None = None  # set only by the logo upload
    console_logo_key: str | None = None


class OrderSettings(_Group):
    auto_advance: bool
    step_minutes: int = Field(ge=1, le=1440)
    delay_chance_pct: int = Field(ge=0, le=100)
    lost_chance_pct: int = Field(ge=0, le=20)
    emails: bool
    fallback_pkr_rate: float = Field(ge=1, le=10000)


class RuntimeSettings(_Group):
    email: EmailSettings
    ai: AiSettings
    operations: OperationsSettings
    branding: BrandingSettings
    orders: OrderSettings
    knowledge_base: KnowledgeBaseSettings
    access: AccessSettings = Field(default_factory=default_access)
