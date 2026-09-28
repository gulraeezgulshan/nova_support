"""Policy numbers shown read-only in Settings, with the document they come from."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Document, DocumentVersion, VersionStatus
from src.api.schemas import PolicyFactOut
from storefront.config import storefront_config


async def policy_facts(db: AsyncSession) -> list[PolicyFactOut]:
    c = storefront_config()
    rows = [
        (
            "Warranty",
            f"{c.warranty.months} months (VoltCare+ {c.warranty.extended_months})",
            "WAR-POL-02",
        ),
        ("Return window", f"{c.returns.window_days} days from delivery", "REF-POL-01"),
        (
            "Refund time",
            f"{c.returns.refund_min_days} to {c.returns.refund_max_days} business days",
            "REF-POL-01",
        ),
        ("Standard delivery", f"{c.shipping.standard_days} business days", "DEL-POL-04"),
        ("Express delivery", f"{c.shipping.express_days} business days", "DEL-POL-04"),
        (
            "Late-delivery credit",
            f"{c.shipping.late_credit_pct}% up to USD {c.shipping.late_credit_cap_usd}",
            "DEL-POL-04",
        ),
    ]
    result = await db.execute(
        select(Document.doc_code, DocumentVersion.version)
        .join(DocumentVersion, DocumentVersion.document_id == Document.id)
        .where(DocumentVersion.status == VersionStatus.ACTIVE)
    )
    active = {code: version for code, version in result.all()}
    return [PolicyFactOut(fact=f, value=v, source=s, version=active.get(s)) for f, v, s in rows]
