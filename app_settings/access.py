"""Page access: which staff roles may view or edit each page of the staff console.

Administrators always have full access and customers never reach staff pages, so the matrix
only holds the three staff roles. Stored data is read tolerantly (a bad entry falls back to
that page's default); updates from the Page access screen are checked strictly.
"""

from dataclasses import dataclass
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from database.models import Role

Level = Literal["none", "view", "edit"]
Needed = Literal["view", "edit"]
PageKey = Literal[
    "dashboard",
    "complaints",
    "review",
    "enquiries",
    "mailbox",
    "orders",
    "imports",
    "analytics",
    "reports",
    "knowledge_base",
    "taxonomy",
    "rules",
    "products",
    "users",
]
AccessKey = PageKey | Literal["settings", "access"]
EDITABLE_ROLES: tuple[str, ...] = ("agent", "reviewer", "manager")
_LEVELS: tuple[str, ...] = get_args(Level)
_RANK = {"none": 0, "view": 1, "edit": 2}


@dataclass(frozen=True)
class PageInfo:
    key: PageKey
    label: str
    description: str
    has_edit: bool
    default: dict[str, Level]


def _page(key: PageKey, label: str, description: str, has_edit: bool, a: Level, r: Level,
          m: Level) -> PageInfo:  # fmt: skip
    return PageInfo(key, label, description, has_edit, {"agent": a, "reviewer": r, "manager": m})


PAGES: tuple[PageInfo, ...] = (
    _page("dashboard", "Dashboard", "Your own dashboard figures", False, "view", "view", "view"),
    _page("complaints", "Complaint queue",
          "View complaints, analysis and checks / log complaints, change status, re-run analysis",
          True, "edit", "edit", "edit"),
    _page("review", "Manual review", "View the review queue / make reviewer decisions",
          True, "none", "edit", "edit"),
    _page("enquiries", "Enquiries", "View the inbox / update or convert enquiries",
          True, "edit", "edit", "edit"),
    _page("mailbox", "Mailbox", "View received and sent e-mails / process an e-mail",
          True, "edit", "edit", "edit"),
    _page("orders", "Orders", "View orders and history / order actions",
          True, "edit", "edit", "edit"),
    _page("imports", "Import complaints", "View templates and imports / upload and import",
          True, "none", "none", "edit"),
    _page("analytics", "Analytics", "Analytics and the organisation-wide dashboard",
          False, "none", "view", "view"),
    _page("reports", "Reports", "View and export reports", False, "none", "view", "view"),
    _page("knowledge_base", "Knowledge base",
          "View documents and passages / upload, activate, retire", True, "view", "view", "view"),
    _page("taxonomy", "Taxonomy & SLAs",
          "View categories, departments and SLAs / change them", True, "view", "view", "view"),
    _page("rules", "Rule matrix", "View rules / edit rules", True, "view", "view", "view"),
    _page("products", "Products", "View products / edit products",
          True, "none", "none", "none"),
    _page("users", "Users & roles",
          "View the user list (changing roles is Administrator only)",
          False, "none", "none", "view"),
)  # fmt: skip
PAGE_KEYS: tuple[PageKey, ...] = tuple(p.key for p in PAGES)
_BY_KEY = {p.key: p for p in PAGES}


def page_info(key: str) -> PageInfo:
    return _BY_KEY[key]  # type: ignore[index]


class PageAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: Level
    reviewer: Level
    manager: Level


def _default(key: str) -> Any:
    return Field(default_factory=lambda: PageAccess(**_BY_KEY[key].default))  # type: ignore[index]


class AccessSettings(BaseModel):
    """The stored matrix. Reading never fails: bad entries fall back per page and role."""

    model_config = ConfigDict(extra="ignore")
    dashboard: PageAccess = _default("dashboard")
    complaints: PageAccess = _default("complaints")
    review: PageAccess = _default("review")
    enquiries: PageAccess = _default("enquiries")
    mailbox: PageAccess = _default("mailbox")
    orders: PageAccess = _default("orders")
    imports: PageAccess = _default("imports")
    analytics: PageAccess = _default("analytics")
    reports: PageAccess = _default("reports")
    knowledge_base: PageAccess = _default("knowledge_base")
    taxonomy: PageAccess = _default("taxonomy")
    rules: PageAccess = _default("rules")
    products: PageAccess = _default("products")
    users: PageAccess = _default("users")

    @model_validator(mode="before")
    @classmethod
    def _tolerant(cls, data: Any) -> Any:
        if isinstance(data, BaseModel):
            data = data.model_dump()
        stored = data if isinstance(data, dict) else {}
        clean: dict[str, dict[str, str]] = {}
        for page in PAGES:
            given = stored.get(page.key)
            given = given.model_dump() if isinstance(given, BaseModel) else given
            given = given if isinstance(given, dict) else {}
            entry = {}
            for role in EDITABLE_ROLES:
                level = given.get(role)
                level = level if level in _LEVELS else page.default[role]
                if level == "edit" and not page.has_edit:
                    level = "view"
                entry[role] = level
            clean[page.key] = entry
        return clean

    def level(self, page: PageKey, role: str) -> Level:
        level: Level = getattr(getattr(self, page), role)
        return level


def default_access() -> AccessSettings:
    return AccessSettings()


def validate_update(matrix: dict[str, dict[str, str]]) -> AccessSettings:
    """A full matrix from the Page access screen; anything unexpected is refused."""
    extra = set(matrix) - set(PAGE_KEYS)
    if extra:
        raise ValueError(f"Unknown page: {', '.join(sorted(extra))}")
    for page in PAGES:
        entry = matrix.get(page.key)
        if not isinstance(entry, dict):
            raise ValueError(f"{page.label}: missing")
        if set(entry) != set(EDITABLE_ROLES):
            raise ValueError(f"{page.label}: give exactly agent, reviewer and manager")
        for level in entry.values():
            if level not in _LEVELS:
                raise ValueError(f"{page.label}: {level!r} is not none, view or edit")
            if level == "edit" and not page.has_edit:
                raise ValueError(f"{page.label} has nothing to edit; use view")
    return AccessSettings.model_validate(matrix)


def level_for(role: Role, page: AccessKey) -> Level:
    if role == Role.ADMIN:
        return "edit"
    if role == Role.CUSTOMER or page in ("settings", "access"):
        return "none"
    from app_settings.store import runtime  # store imports the model, which imports this

    return runtime().access.level(page, role.value)  # type: ignore[arg-type]


def allowed(role: Role, page: AccessKey, needed: Needed) -> bool:
    return _RANK[level_for(role, page)] >= _RANK[needed]


def permissions_for(role: Role) -> dict[str, Level]:
    keys: tuple[AccessKey, ...] = (*PAGE_KEYS, "settings", "access")
    return {key: level_for(role, key) for key in keys}
