"""Application settings, loaded from environment variables (and `.env` in development).

Every secret or deployment-specific value lives here. The app refuses to start when a
required value is missing, so misconfiguration fails fast instead of at request time.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
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

    # GenAI pipeline (the model is configuration, not code)
    genai_provider: Literal["anthropic"] = "anthropic"
    genai_model: str = "claude-opus-5"
    genai_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    genai_timeout_seconds: float = 60.0
    genai_max_attempts: int = Field(default=2, ge=1, le=3)  # 1 call + 1 repair retry
    anthropic_api_key: str | None = None

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
