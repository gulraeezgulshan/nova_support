"""Application settings, loaded from environment variables (and `.env` in development).

Every secret or deployment-specific value lives here. The app refuses to start when a
required value is missing, so misconfiguration fails fast instead of at request time.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # Comma-separated list of browser origins allowed to call the API (CORS).
    allowed_origins: str = "http://localhost:3000"

    # Database / queue
    database_url: str = "postgresql+psycopg://supportnova:supportnova@localhost:5432/supportnova"
    redis_url: str = "redis://localhost:6379/0"

    # Clerk authentication. The issuer is the Clerk "Frontend API" URL,
    # e.g. https://your-app.clerk.accounts.dev (dev) or https://clerk.yourdomain.com (prod).
    clerk_issuer: str = ""
    clerk_authorized_parties: str = "http://localhost:3000"
    clerk_webhook_signing_secret: str = ""
    # Users signing in with these e-mails are provisioned as administrators.
    bootstrap_admin_emails: str = ""

    # File storage: "local" for development/tests, "s3" for MinIO / Cloudflare R2.
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_dir: Path = ROOT_DIR / ".data" / "storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "supportnova"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_region: str = "auto"

    # Knowledge base
    max_upload_mb: int = Field(default=20, ge=1, le=200)
    embedding_provider: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    chunk_max_tokens: int = 450
    chunk_overlap_tokens: int = 60
    retrieval_limit: int = 8

    # GenAI pipeline. The provider is one setting; each provider keeps its own model and key,
    # so switching between Claude and OpenAI is a one-line change.
    genai_provider: Literal["anthropic", "openai"] = "anthropic"
    # none and minimal are OpenAI-only (Claude uses low for both).
    genai_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"] = "low"
    genai_timeout_seconds: float = 60.0
    genai_max_attempts: int = Field(default=2, ge=1, le=3)  # 1 call + 1 repair retry
    anthropic_api_key: str | None = None
    # GENAI_MODEL is the name used before OpenAI support was added.
    anthropic_model: str = Field(
        default="claude-opus-5", validation_alias=AliasChoices("ANTHROPIC_MODEL", "GENAI_MODEL")
    )
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    # Send the reasoning effort (GENAI_EFFORT). Turn off for models without reasoning support.
    openai_reasoning: bool = True

    # Support mailbox (e-mail complaints). Unset → the scheduled check does nothing and
    # outgoing e-mails are recorded as not_configured.
    mail_imap_host: str | None = None
    mail_imap_port: int = 993
    mail_smtp_host: str | None = None
    mail_smtp_port: int = 465  # 465 = SSL, 587 = STARTTLS
    mail_username: str | None = None
    mail_password: str | None = None  # an app password; never logged or returned
    mail_from_name: str = "VoltHaven Customer Care"
    # How replies are sent: SMTP, or Brevo's HTTPS API for hosts that block outbound SMTP
    # (Railway below the Pro plan). Reading always uses IMAP.
    mail_send_via: Literal["smtp", "brevo"] = "smtp"
    brevo_api_key: str | None = None  # never logged or returned

    @property
    def mailbox_configured(self) -> bool:
        sending = self.brevo_api_key if self.mail_send_via == "brevo" else self.mail_smtp_host
        return bool(self.mail_imap_host and sending and self.mail_username and self.mail_password)

    @property
    def genai_model(self) -> str:
        return self.openai_model if self.genai_provider == "openai" else self.anthropic_model

    @property
    def genai_api_key(self) -> str | None:
        """The API key of the selected provider (None means the GenAI pipeline is off)."""
        key = self.openai_api_key if self.genai_provider == "openai" else self.anthropic_api_key
        return key or None

    @property
    def genai_api_key_name(self) -> str:
        return "OPENAI_API_KEY" if self.genai_provider == "openai" else "ANTHROPIC_API_KEY"

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, value: str) -> str:
        """Hosting platforms hand out postgres:// URLs; SQLAlchemy needs the driver named."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @model_validator(mode="after")
    def _production_ready(self) -> "Settings":
        """Refuse to start a production deployment that is missing something essential."""
        if self.environment != "production":
            return self
        problems = []
        if not self.clerk_issuer or "your-app" in self.clerk_issuer:
            problems.append("CLERK_ISSUER must be your Clerk Frontend API URL")
        if any("localhost" in origin for origin in self.cors_origins):
            problems.append("ALLOWED_ORIGINS must be the deployed web address, not localhost")
        if self.storage_backend != "s3" or not (
            self.s3_endpoint_url and self.s3_access_key_id and self.s3_secret_access_key
        ):
            problems.append(
                "STORAGE_BACKEND=s3 with S3_ENDPOINT_URL, S3_ACCESS_KEY_ID and "
                "S3_SECRET_ACCESS_KEY is required (container disks are not persistent)"
            )
        if problems:
            raise ValueError("Production configuration incomplete: " + "; ".join(problems))
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return _split_csv(self.allowed_origins)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def clerk_authorized_party_list(self) -> list[str]:
        return _split_csv(self.clerk_authorized_parties)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bootstrap_admin_email_set(self) -> set[str]:
        return {e.lower() for e in _split_csv(self.bootstrap_admin_emails)}

    @property
    def clerk_jwks_url(self) -> str:
        return f"{self.clerk_issuer.rstrip('/')}/.well-known/jwks.json"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
