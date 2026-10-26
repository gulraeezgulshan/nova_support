"""Settings administrators change at run time (the staff Settings page)."""

import re
from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app_settings.access import AccessSettings, default_access
from app_settings.patterns import PROMISE_KINDS, regex_problem

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


COMPENSATION_TYPES: tuple[str, ...] = (
    "store_credit",
    "shipping_fee_refund",
    "partial_refund",
    "full_refund",
    "replacement",
    "repair",
    "voucher",
)
ESCALATION_ACTIONS: tuple[str, ...] = (
    "ESCALATE_TO_SUPERVISOR",
    "ESCALATE_TO_MANAGER",
    "ESCALATE_TO_SPECIALIST",
    "ESCALATE_TO_COMPLIANCE",
    "ESCALATE_TO_CRITICAL_MANAGEMENT",
)


def _known_actions() -> set[str]:
    from src.core.domain import actions  # local: domain is loaded after the settings model

    return set(actions())


def known_signals() -> set[str]:
    """Risk-signal names a signal boost may use (config/detectors.yaml)."""
    import yaml

    from src.core.config import ROOT_DIR

    with (ROOT_DIR / "config" / "detectors.yaml").open(encoding="utf-8") as handle:
        return set(yaml.safe_load(handle)["signals"])


def _check_actions(codes: list[str], where: str) -> None:
    unknown = sorted(set(codes) - _known_actions())
    if unknown:
        raise ValueError(f"{where}: unknown action {', '.join(unknown)}")
    if len(set(codes)) != len(codes):
        raise ValueError(f"{where}: each action only once")


class ScoreWeights(_Group):
    critical: int = Field(ge=1, le=10)
    major: int = Field(ge=1, le=10)
    minor: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def _ordered(self) -> "ScoreWeights":
        if not self.critical >= self.major >= self.minor:
            raise ValueError("weights must be critical ≥ major ≥ minor")
        return self


class CompensationLimit(_Group):
    requires_any: list[str] = Field(min_length=1, max_length=20)
    max_pct_of_order: float | None = Field(default=None, ge=0, le=100)
    max_amount: float | None = Field(default=None, ge=0, le=10000)


class SignalBoost(_Group):
    category: Annotated[str, Field(min_length=1, max_length=40)]
    subcategory: Annotated[str, Field(min_length=1, max_length=60)]
    weight: int = Field(ge=1, le=5)


class ValidationSettings(_Group):
    """Numbers and lists Python's validation and classifier use (patterns stay in YAML)."""

    score_weights: ScoreWeights
    compensation: dict[str, CompensationLimit]
    never_allowed_actions: list[str] = Field(max_length=60)
    orders_required_for: list[str] = Field(max_length=30)
    escalation_action_levels: dict[str, int]
    classifier_confident: int = Field(ge=1, le=10)
    classifier_secondary: int = Field(ge=1, le=10)
    signal_boosts: dict[str, SignalBoost] = Field(max_length=14)

    @model_validator(mode="after")
    def _consistent(self) -> "ValidationSettings":
        if set(self.compensation) != set(COMPENSATION_TYPES):
            raise ValueError(f"compensation must list exactly: {', '.join(COMPENSATION_TYPES)}")
        for kind, limit in self.compensation.items():
            _check_actions(limit.requires_any, f"compensation {kind}")
        _check_actions(self.never_allowed_actions, "never-allowed actions")
        if len(set(self.orders_required_for)) != len(self.orders_required_for):
            raise ValueError("needs an order: each category only once")
        if set(self.escalation_action_levels) != set(ESCALATION_ACTIONS):
            raise ValueError(
                f"escalation levels must list exactly: {', '.join(ESCALATION_ACTIONS)}"
            )
        bad_levels = [k for k, v in self.escalation_action_levels.items() if not 1 <= v <= 5]
        if bad_levels:
            raise ValueError(f"escalation levels must be 1 to 5: {', '.join(bad_levels)}")
        unknown = sorted(set(self.signal_boosts) - known_signals())
        if unknown:
            raise ValueError(f"signal boosts: unknown signal {', '.join(unknown)}")
        return self


def _pattern_text(value: str) -> str:
    value = _one_line(value)
    if not 1 <= len(value) <= 300:
        raise ValueError("must be 1 to 300 characters")
    return value


class PatternEntry(_Group):
    """A plain phrase (matched literally) or a regular expression."""

    text: Annotated[str, AfterValidator(_pattern_text)]
    mode: Literal["phrase", "regex"]


class WeightedEntry(PatternEntry):
    weight: int = Field(ge=1, le=3)  # 3 decisive, 2 strong hint, 1 weak hint


class PromisePatterns(_Group):
    commitment: list[PatternEntry]
    conditional: list[PatternEntry]
    kinds: dict[str, list[PatternEntry]]
    deadline: Annotated[str, Field(min_length=1, max_length=300)]  # regex with 3 groups


def _check_list(where: str, entries: Sequence[PatternEntry], low: int, high: int) -> None:
    if not low <= len(entries) <= high:
        raise ValueError(f"{where}: {low} to {high} entries")
    seen: set[tuple[str, str]] = set()
    for number, entry in enumerate(entries, start=1):
        if entry.mode == "regex" and (problem := regex_problem(entry.text)):
            raise ValueError(f"{where}, entry {number}: {problem}")
        if (entry.mode, entry.text) in seen:
            raise ValueError(f"{where}: entry {number} is listed twice")
        seen.add((entry.mode, entry.text))


class PatternSettings(_Group):
    """Risk-signal words, classifier phrases and promise wording (Settings → Patterns)."""

    signals: dict[str, list[PatternEntry]]
    classifier: dict[str, dict[str, list[WeightedEntry]]]
    promises: PromisePatterns

    @model_validator(mode="after")
    def _consistent(self) -> "PatternSettings":
        names = known_signals()
        if set(self.signals) != names:
            raise ValueError(f"signals must list exactly: {', '.join(sorted(names))}")
        for name, entries in self.signals.items():
            _check_list(name, entries, 1, 80)
        for category, subs in self.classifier.items():
            for subcategory, weighted in subs.items():
                _check_list(f"Classifier {category}/{subcategory}", weighted, 0, 40)
        p = self.promises
        _check_list("Promises commitment", p.commitment, 1, 30)
        _check_list("Promises conditional", p.conditional, 1, 30)
        if set(p.kinds) != set(PROMISE_KINDS):
            raise ValueError(f"promise kinds must be exactly: {', '.join(PROMISE_KINDS)}")
        for kind, entries in p.kinds.items():
            _check_list(f"Promises kind {kind}", entries, 1, 30)
        if problem := regex_problem(p.deadline):
            raise ValueError(f"Deadline: {problem}")
        if re.compile(p.deadline).groups != 3:
            raise ValueError("Deadline must keep its 3 groups (amount, business/working, unit).")
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
    validation: ValidationSettings
    patterns: PatternSettings
    access: AccessSettings = Field(default_factory=default_access)
