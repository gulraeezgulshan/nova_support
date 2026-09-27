"""Shop facts match the knowledge-base policy documents, word for word where it matters."""

from src.core.config import ROOT_DIR
from storefront.config import storefront_config

SOURCES = ROOT_DIR / "sample_documents" / "sources"


def doc(code: str) -> str:
    [path] = list(SOURCES.glob(f"{code}_*.md"))
    return path.read_text(encoding="utf-8")


def test_delivery_numbers_match_the_delivery_policy() -> None:
    s = storefront_config().shipping
    text = doc("DEL-POL-04")
    assert f"Standard delivery arrives within {s.standard_days} business days" in text
    assert f"Express delivery arrives within {s.express_days} business days" in text
    assert f"more than {s.late_threshold_days} business days after the committed" in text
    assert (
        f"store credit of {s.late_credit_pct}% of the order value, "
        f"up to a maximum of USD {s.late_credit_cap_usd}"
    ) in text
    assert f"{s.lost_after_days} consecutive business days is treated as lost" in text
    assert f"tracking number by e-mail within {s.tracking_hours} hours of dispatch" in text
    assert f"reported within {s.damage_report_hours} hours of delivery" in text


def test_return_and_refund_numbers_match_the_refund_policy() -> None:
    r = storefront_config().returns
    text = doc("REF-POL-01")
    assert f"returned within {r.window_days} days of delivery" in text
    assert f"within {r.refund_min_days} to {r.refund_max_days} business days" in text
    assert f"Store-credit refunds are issued within {r.store_credit_days} business day" in text
    assert f"when reported within {r.defect_report_days} days of delivery" in text


def test_warranty_numbers_match_the_warranty_policy() -> None:
    w = storefront_config().warranty
    text = doc("WAR-POL-02")
    assert f"{w.months}-month limited warranty" in text
    assert f"extended warranty of {w.extended_months} months" in text
    assert f"reported within {w.replacement_days} days of delivery is replaced" in text
    assert f"completed within {w.repair_days} business days" in text


def test_faq_placeholders_are_filled() -> None:
    faq = storefront_config().faq
    assert faq
    for item in faq:
        assert "{" not in item.answer, item.question


def test_checkout_uses_the_configured_delivery_days() -> None:
    from storefront.orders import SHIPPING_DAYS

    s = storefront_config().shipping
    assert {"standard": s.standard_days, "express": s.express_days} == SHIPPING_DAYS
