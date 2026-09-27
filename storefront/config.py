"""Shop facts (company details, delivery, returns, warranty, FAQ) from config/storefront.yaml.

Served to the website by `GET /storefront/config`; checkout reads its delivery days from here.
"""

from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from src.core.config import ROOT_DIR


class Social(BaseModel):
    name: str
    url: str


class Company(BaseModel):
    name: str
    tagline: str
    address: str
    phone: str
    support_email: str
    hours: str
    socials: list[Social]


class Shipping(BaseModel):
    standard_days: int
    express_days: int
    late_threshold_days: int
    late_credit_pct: int
    late_credit_cap_usd: int
    lost_after_days: int
    tracking_hours: int
    damage_report_hours: int


class Returns(BaseModel):
    window_days: int
    refund_min_days: int
    refund_max_days: int
    store_credit_days: int
    defect_report_days: int


class Warranty(BaseModel):
    months: int
    extended_months: int
    replacement_days: int
    repair_days: int


class FaqItem(BaseModel):
    question: str
    answer: str


class StorefrontConfig(BaseModel):
    company: Company
    shipping: Shipping
    returns: Returns
    warranty: Warranty
    faq: list[FaqItem]


@lru_cache
def storefront_config() -> StorefrontConfig:
    with (ROOT_DIR / "config" / "storefront.yaml").open(encoding="utf-8") as handle:
        raw: dict[str, Any] = yaml.safe_load(handle)
    values = {**raw["shipping"], **raw["returns"], **raw["warranty"]}
    raw["faq"] = [{**f, "answer": f["answer"].format(**values)} for f in raw["faq"]]
    return StorefrontConfig.model_validate(raw)
