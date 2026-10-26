"""Page access matrix: catalogue, defaults, tolerant loading, strict updates, role rules."""

import pytest

from app_settings import access, load
from database.models import Role

TODAY = {  # spec section 1: agent, reviewer, manager
    "dashboard": ("view", "view", "view"),
    "complaints": ("edit", "edit", "edit"),
    "review": ("none", "edit", "edit"),
    "enquiries": ("edit", "edit", "edit"),
    "mailbox": ("edit", "edit", "edit"),
    "orders": ("edit", "edit", "edit"),
    "imports": ("none", "none", "edit"),
    "analytics": ("none", "view", "view"),
    "reports": ("none", "view", "view"),
    "knowledge_base": ("view", "view", "view"),
    "taxonomy": ("view", "view", "view"),
    "rules": ("view", "view", "view"),
    "products": ("none", "none", "none"),
    "users": ("none", "none", "view"),
}


def full_matrix() -> dict[str, dict[str, str]]:
    return {k: dict(zip(access.EDITABLE_ROLES, v, strict=True)) for k, v in TODAY.items()}


def test_defaults_match_today() -> None:
    d = access.default_access().model_dump()
    assert {k: (v["agent"], v["reviewer"], v["manager"]) for k, v in d.items()} == TODAY


def test_catalogue_order_and_edit_flags() -> None:
    assert tuple(TODAY) == access.PAGE_KEYS
    view_only = {p.key for p in access.PAGES if not p.has_edit}
    assert view_only == {"dashboard", "analytics", "reports", "users"}


def test_one_bad_page_falls_back_without_touching_others() -> None:
    s = load(
        {
            "access": {"rules": {"agent": "bogus"}, "orders": {"agent": "view"}},
            "email": {"mailbox_check_seconds": 120},
        }
    )
    assert s.access.rules.agent == "view"  # default kept for the bad value
    assert s.access.orders.agent == "view"  # valid change applied
    assert s.access.orders.reviewer == "edit"  # missing role → page default
    assert s.email.mailbox_check_seconds == 120  # other groups untouched


def test_unknown_pages_and_roles_ignored_and_edit_on_view_only_page_is_view() -> None:
    s = load(
        {
            "access": {
                "nope": {"agent": "edit"},
                "analytics": {"agent": "edit", "customer": "edit", "admin": "none"},
            }
        }
    )
    assert s.access.analytics.agent == "view"
    assert s.access.analytics.reviewer == "view"


def test_admin_and_customer_ignore_the_matrix() -> None:
    assert access.level_for(Role.ADMIN, "products") == "edit"
    assert access.level_for(Role.ADMIN, "access") == "edit"
    assert access.level_for(Role.CUSTOMER, "complaints") == "none"
    assert access.level_for(Role.MANAGER, "settings") == "none"


def test_allowed_and_permissions() -> None:
    assert access.allowed(Role.AGENT, "complaints", "edit")
    assert not access.allowed(Role.AGENT, "rules", "edit")
    assert access.allowed(Role.AGENT, "rules", "view")
    p = access.permissions_for(Role.REVIEWER)
    assert p["review"] == "edit" and p["imports"] == "none" and p["access"] == "none"
    assert set(p) == set(TODAY) | {"settings", "access"}


def test_validate_update_is_strict() -> None:
    full = full_matrix()
    assert access.validate_update(full).review.agent == "none"
    bad_cases = [
        {**full, "analytics": {**full["analytics"], "agent": "edit"}},
        {**full, "rules": {**full["rules"], "admin": "none"}},
        {k: v for k, v in full.items() if k != "rules"},
        {**full, "nope": full["rules"]},
        {**full, "rules": {**full["rules"], "agent": "maybe"}},
    ]
    for bad in bad_cases:
        with pytest.raises(ValueError):
            access.validate_update(bad)
