"""Today's behaviour, from environment variables and config files: the settings defaults."""

import yaml

from app_settings.access import default_access
from app_settings.model import RuntimeSettings
from src.core.config import ROOT_DIR

KB_TYPES_FILE = ROOT_DIR / "config" / "knowledge_base.yaml"


def _document_types_file() -> list[dict[str, object]]:
    """The document types shipped in config/knowledge_base.yaml (the defaults)."""
    with KB_TYPES_FILE.open(encoding="utf-8") as handle:
        types: list[dict[str, object]] = yaml.safe_load(handle)["document_types"]
    return types


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def defaults() -> RuntimeSettings:
    # Local imports: these modules import app_settings for their own settings.
    from python_validation.types import validation_config
    from src.core.config import get_settings
    from src.core.domain import analytics_config
    from storefront.config import storefront_config

    env, validation, company = get_settings(), validation_config(), storefront_config().company
    chunk = int(_clamp(env.chunk_max_tokens, 100, 480))
    return RuntimeSettings.model_validate(
        {
            "email": {
                "mailbox_check_seconds": 60,
                "outbox_flush_seconds": 30,
                "from_name": env.mail_from_name,
                "auto_replies": True,
            },
            "ai": {
                "provider": env.genai_provider,
                "model": env.genai_model,
                "effort": env.genai_effort,
                "retrieval_limit": env.retrieval_limit,
                "auto_analysis": True,
                # Environment values may be wider than the Settings limits; keep them in range
                # so an old deployment value can never make every settings read fail.
                "timeout_seconds": _clamp(env.genai_timeout_seconds, 10, 300),
                "max_attempts": int(_clamp(env.genai_max_attempts, 1, 3)),
                "openai_reasoning": env.openai_reasoning,
            },
            "knowledge_base": {
                "chunk_max_tokens": chunk,
                "chunk_overlap_tokens": int(_clamp(env.chunk_overlap_tokens, 0, chunk - 50)),
                "max_upload_mb": int(_clamp(env.max_upload_mb, 1, 50)),
                "retrieval_candidates": 30,
                "rrf_k": 60,
                "document_types": _document_types_file(),
            },
            "operations": {
                "sla_scan_minutes": analytics_config()["sla"]["scan_interval_minutes"],
                "verified_min_score": validation["verified_min_score"],
                "always_review_escalation_level": validation["always_review_escalation_level"],
            },
            "access": default_access().model_dump(),
            "orders": {
                "auto_advance": True,
                "step_minutes": 2,
                "delay_chance_pct": 10,
                "lost_chance_pct": 0,
                "emails": True,
                "fallback_pkr_rate": 280.0,
            },
            "branding": {
                "shop_name": company.name,
                "shop_tagline": company.tagline,
                "console_name": "SupportNova",
                "support_email": company.support_email,
                "phone": company.phone,
                "address": company.address,
                "hours": company.hours,
            },
        }
    )
