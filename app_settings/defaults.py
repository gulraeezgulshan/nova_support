"""Today's behaviour, from environment variables and config files: the settings defaults."""

from typing import Any

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


CLASSIFIER_FILE = ROOT_DIR / "config" / "classification.yaml"


def _validation_defaults(validation: dict[str, Any]) -> dict[str, Any]:
    """The numbers and lists from validation.yaml and classification.yaml (patterns stay there)."""
    with CLASSIFIER_FILE.open(encoding="utf-8") as handle:
        classifier = yaml.safe_load(handle)
    return {
        "score_weights": validation["score_weights"],
        "compensation": {
            kind: {
                "requires_any": rule["requires_any"],
                "max_pct_of_order": rule.get("max_pct_of_order"),
                "max_amount": rule.get("max_amount"),
            }
            for kind, rule in validation["compensation"].items()
        },
        "never_allowed_actions": validation["never_allowed_actions"],
        "orders_required_for": validation["orders_required_for"],
        "escalation_action_levels": validation["escalation_action_levels"],
        "classifier_confident": classifier["thresholds"]["confident"],
        "classifier_secondary": classifier["thresholds"]["secondary"],
        "signal_boosts": {
            signal: {"category": c, "subcategory": sub, "weight": w}
            for signal, (c, sub, w) in classifier.get("signal_boosts", {}).items()
        },
    }


def _pattern_defaults(validation: dict[str, Any]) -> dict[str, Any]:
    """Today's word lists, phrase lists and promise wording, each pattern as a regex entry."""

    def regex(text: str) -> dict[str, str]:
        return {"text": text, "mode": "regex"}

    with CLASSIFIER_FILE.open(encoding="utf-8") as handle:
        classifier = yaml.safe_load(handle)["subcategories"]
    with (ROOT_DIR / "config" / "detectors.yaml").open(encoding="utf-8") as handle:
        signals = yaml.safe_load(handle)["signals"]
    promises = validation["promises"]
    return {
        "signals": {name: [regex(p) for p in spec["patterns"]] for name, spec in signals.items()},
        "classifier": {
            category: {
                sub: [{**regex(text), "weight": weight} for weight, text in entries]
                for sub, entries in subs.items()
            }
            for category, subs in classifier.items()
        },
        "promises": {
            "commitment": [regex(promises["commitment"])],
            "conditional": [regex(promises["conditional"])],
            "kinds": {k: [regex(spec["pattern"])] for k, spec in promises["kinds"].items()},
            "deadline": promises["deadline"],
        },
    }


# Today's limits (they were constants in the intake, chat and import modules).
INTAKE_DEFAULTS: dict[str, Any] = {
    "near_duplicate_min_ratio": 88,
    "related_min_similarity": 0.80,
    "duplicate_window_days": 30,
    "repeat_window_days": 60,
    "repeat_min_gap_hours": 24,
    "min_title_chars": 5,
    "min_description_chars": 20,
    "min_description_words": 5,
    "max_description_chars": 5000,
    "max_attachments": 5,
    "max_attachment_mb": 5,
    "chat_max_questions": 6,
    "chat_max_message_chars": 2000,
    "chat_max_customer_messages": 30,
    "import_max_rows": 1000,
}


def _analytics_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    trends = cfg["trends"]
    return {
        "trend_window_days": trends["window_days"],
        "trend_min_count": trends["min_count"],
        "trend_rise_ratio": trends["rise_ratio"],
        "recurring_min_count": trends["recurring_min_count"],
        "watched_categories": trends["watched_categories"],
        "dashboard_list_limit": cfg["dashboard"]["list_limit"],
        "first_response_statuses": cfg["sla"]["first_response_statuses"],
        "resolved_statuses": cfg["sla"]["resolved_statuses"],
    }


def _shop_defaults() -> dict[str, Any]:
    """Socials and the FAQ as written in storefront.yaml (answers keep their placeholders)."""
    with (ROOT_DIR / "config" / "storefront.yaml").open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    return {"best_seller_days": 90, "socials": raw["company"]["socials"], "faq": raw["faq"]}


# Today's chat lines and complaint e-mails; "{shop}" is the Branding shop name.
COMPLAINT_EMAIL_DEFAULTS: dict[str, str] = {
    "acknowledgement": (
        "Hello {name},\n\nThank you for contacting {shop}. We have received your complaint "
        "and its reference is {ref}. Our team is looking into it and we will reply in this "
        "e-mail thread. If you have photos or documents, reply to this e-mail with them "
        "attached."
    ),
    "holding": (
        "Hello {name},\n\nA specialist is reviewing your complaint {ref}. We will reply in "
        "this thread as soon as the review is complete."
    ),
    "rejected": (
        "Hello {name},\n\nThank you for your e-mail. We could not open a complaint yet: "
        "{reason}\n\nPlease reply with what happened, when it happened and what you would "
        "like us to do."
    ),
    "duplicate": (
        "Hello {name},\n\nThis matches a complaint you already sent us, reference {ref}. We "
        "are working on it and will reply in that thread."
    ),
    "signature": "Kind regards,\n{shop} Customer Care",
}
CHAT_DEFAULTS: dict[str, Any] = {
    "greeting": "Hi, I'm the {shop} support assistant. Which order is this about?",
    "ask_what_happened": "Sorry to hear there's a problem with your {product}. What happened?",
    "fallback_questions": [
        "What happened? Please describe the problem.",
        "When did this happen?",
        "What would you like us to do about it?",
    ],
    "neutral_question": "Thanks. Is there anything else about the problem we should know?",
    "summary_lead": "Thanks, here is what I'll send to our team:",
    "faq_follow_up": (
        "Is there anything else I can help with, or would you like to report a problem?"
    ),
    "added_to_complaint": "Added to your complaint {ref}. To ask something new, tap New question.",
    "submitted": (
        "Thanks, I've sent this to our team. Your complaint reference is {ref}. I'll post the "
        "reply here as soon as it's ready. You can add photos or documents to it from My "
        "complaints."
    ),
}


def _text_defaults() -> dict[str, Any]:
    with (ROOT_DIR / "config" / "order_emails.yaml").open(encoding="utf-8") as handle:
        order_emails = yaml.safe_load(handle)
    return {
        "order_emails": order_emails,
        "complaint_emails": COMPLAINT_EMAIL_DEFAULTS,
        "chat": CHAT_DEFAULTS,
    }


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
            "analytics": _analytics_defaults(analytics_config()),
            "intake": INTAKE_DEFAULTS,
            "shop": _shop_defaults(),
            "texts": _text_defaults(),
            "validation": _validation_defaults(validation),
            "patterns": _pattern_defaults(validation),
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
