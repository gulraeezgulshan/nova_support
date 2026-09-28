"""Settings administrators change at run time (the staff Settings page)."""

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _model_matches_provider(self) -> "AiSettings":
        other = "anthropic" if self.provider == "openai" else "openai"
        if self.model in SUGGESTED_MODELS[other]:
            label = "an Anthropic" if other == "anthropic" else "an OpenAI"
            raise ValueError(f"{self.model} is {label} model; choose one for {self.provider}")
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


class RuntimeSettings(_Group):
    email: EmailSettings
    ai: AiSettings
    operations: OperationsSettings
    branding: BrandingSettings
