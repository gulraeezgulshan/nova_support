"""The facts rule conditions may refer to.

Facts are computed deterministically in Python from the complaint, the customer, the order
and the risk-signal detectors, never by the GenAI model. A condition that mentions an
unknown fact is rejected when the rule is saved, so a typo can't silently disable a rule.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FactSpec:
    type: str  # str | int | float | bool | list[str]
    description: str


FACTS: dict[str, FactSpec] = {
    # classification (candidate category being evaluated)
    "category": FactSpec("str", "Complaint category code, e.g. DELIVERY"),
    "subcategory": FactSpec("str", "Subcategory code, e.g. DELAYED_DELIVERY"),
    "issue_categories": FactSpec("list[str]", "Categories of all issues (primary + secondary)"),
    # customer
    "customer_type": FactSpec("str", "STANDARD, VOLTCARE_PLUS, VIP or BUSINESS"),
    "is_vip": FactSpec("bool", "Customer type is VIP"),
    "repeat_count": FactSpec("int", "Earlier complaints by this customer in the last 60 days"),
    "unresolved_repeat_count": FactSpec("int", "Earlier complaints in 60 days not yet resolved"),
    # order
    "has_order": FactSpec("bool", "A valid order is linked to the complaint"),
    "order_status": FactSpec("str", "processing, shipped, delivered, lost or returned"),
    "order_amount": FactSpec("float", "Order value in USD"),
    "shipping_method": FactSpec("str", "standard or express"),
    "days_since_order": FactSpec("int", "Calendar days from order date to complaint"),
    "days_since_delivery": FactSpec("int", "Calendar days from delivery to complaint"),
    "days_late": FactSpec("int", "Business days after the committed delivery date"),
    "disputed_amount": FactSpec("float", "Largest money amount mentioned in the complaint"),
    # deterministic risk signals (config/detectors.yaml)
    "safety_hazard": FactSpec("bool", "Heat, fire, smoke, sparks, swelling, shock"),
    "injury": FactSpec("bool", "Person hurt or property damaged"),
    "privacy_exposure": FactSpec("bool", "Personal data exposed to someone else"),
    "account_compromise": FactSpec("bool", "Unauthorised account access or transactions"),
    "legal_threat": FactSpec("bool", "Mentions lawyers, courts or regulators"),
    "repeat_contact": FactSpec("bool", "Customer says the issue was raised before"),
    "cancellation_threat": FactSpec("bool", "Customer threatens to leave"),
    "emotional_intensity": FactSpec("bool", "Strong emotional wording (never urgency by itself)"),
    "prompt_injection": FactSpec("bool", "Text tries to instruct the AI or impersonate staff"),
    "policy_claim": FactSpec("bool", "Customer asserts a policy or prior promise"),
    "repeated_repair": FactSpec("bool", "Same fault repaired before"),
    "requests_refund": FactSpec("bool", "Customer asks for money back"),
    "requests_replacement": FactSpec("bool", "Customer asks for a replacement"),
    "requests_compensation": FactSpec("bool", "Customer asks for compensation"),
}
