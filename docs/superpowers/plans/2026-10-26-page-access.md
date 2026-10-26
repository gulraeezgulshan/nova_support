# Page Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Administrators choose, per staff role, which console pages each role may view or edit; the API enforces it and the website follows it.

**Architecture:** A page catalogue and an `access` group in the existing run-time settings (`app_settings`) hold the matrix. A `require_access(page, level)` dependency replaces the hard-coded `require_roles(...)` lists in the route modules. `/me` returns the user's permissions, which drive the sidebar, page guards and edit buttons. A new admin page edits the matrix.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2 (async), pytest; Next.js 16 App Router, TanStack Query, generated @hey-api client, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-10-26-page-access-design.md`

## Global Constraints

- Levels: `none` < `view` < `edit`; edit includes view. Editable roles: `agent`, `reviewer`, `manager`.
- Page keys (exactly): `dashboard`, `complaints`, `review`, `enquiries`, `mailbox`, `orders`, `imports`, `analytics`, `reports`, `knowledge_base`, `taxonomy`, `rules`, `products`, `users`.
- Pages without edit: `dashboard`, `analytics`, `reports`, `users` (a stored or submitted `edit` is read as `view` / rejected with 422).
- Defaults reproduce today's access exactly (spec section 1 table).
- Administrators always `edit` on every page; customers always `none`; the matrix is never consulted for either.
- Admin only, not in the matrix: `GET/PUT /settings`, logo upload/delete, `GET/PUT /access`, `PATCH /users/{id}`.
- Shared lookups stay open to every signed-in staff member: `GET /taxonomy/departments`, `GET /taxonomy/categories`, `GET /taxonomy/vocabulary`, `GET /me`.
- Denied: HTTP 403, detail exactly `"You don't have access to this page"`.
- Audit action for matrix saves: `access.updated` (before/after of the `access` group only).
- Web copy: page title "Page access" at `/settings/access`; save toast "Saved. Applies within 15 seconds"; conflict "Someone else changed the settings. Reload to see their changes."; no-access panel "You don't have access to this page. Ask an administrator."
- Commits: one per task, no `Co-Authored-By` line (Vercel blocks unlinked authors).

## Review Focus

- A staff route left on an old hard-coded role list (or a new route added later) silently ignores the matrix → Task 3 adds a route-inventory test that fails for any staff route not gated by `require_access`, not admin-locked, and not in the shared/mixed allowlist.
- An admin saves the matrix and the same API process keeps serving the old matrix → Task 4 tests that a request right after `PUT /access` sees the change.
- A Settings-page save silently resets the matrix to defaults (the Settings PUT rebuilds `RuntimeSettings`) → Task 1 tests that `PUT /settings` keeps a changed `access` group.
- A role whose Dashboard is `none` signs in and lands on `/dashboard` → Task 5's browser check confirms the no-access panel renders (no crash, no redirect loop) and the sidebar hides empty groups.
- A role with View but not Edit opens a complaint/order/rule page and edit controls still show and then fail with 403 → Task 5's browser check covers a view-only role on complaints and orders.

---

### Task 1: Page catalogue, `access` settings group and saving

**Files:**
- Create: `app_settings/access.py`
- Modify: `app_settings/model.py` (add `access` to `RuntimeSettings`), `app_settings/defaults.py` (add `"access"`), `app_settings/store.py` (`save` audit parameters), `app_settings/__init__.py` (exports), `src/api/routes/settings.py` (`update_settings` keeps `access`)
- Test: `tests/unit/test_access_model.py`, `tests/integration/test_settings_api.py` (one new test)

**Interfaces:**
- Produces (in `app_settings/access.py`):
  - `Level = Literal["none", "view", "edit"]`; `Needed = Literal["view", "edit"]`
  - `PageKey = Literal[...the 14 keys...]`; `AccessKey = PageKey | Literal["settings", "access"]`
  - `EDITABLE_ROLES: tuple[str, ...] = ("agent", "reviewer", "manager")`
  - `@dataclass(frozen=True) class PageInfo: key: PageKey; label: str; description: str; has_edit: bool; default: dict[str, Level]`
  - `PAGES: tuple[PageInfo, ...]` (spec order), `PAGE_KEYS: tuple[PageKey, ...]`, `page_info(key: str) -> PageInfo`
  - `class PageAccess(BaseModel)`: `agent: Level`, `reviewer: Level`, `manager: Level` (extra forbidden)
  - `class AccessSettings(BaseModel)`: one `PageAccess` field per page key, defaulting to that page's default; a `model_validator(mode="before")` that, per page, merges the stored roles over the page default, drops unknown pages/roles, replaces an invalid level with the default for that role, and turns `edit` into `view` on pages without edit. It never raises.
  - `default_access() -> AccessSettings`
  - `validate_update(matrix: dict[str, dict[str, str]]) -> AccessSettings` (strict: every page and role present, no extra keys, valid levels, no `edit` on view-only pages; raises `ValueError` with a message naming the page)
  - `level_for(role: Role, page: AccessKey) -> Level` (admin → `edit`; customer → `none`; `settings`/`access` → `none` for non-admins; otherwise `runtime().access`)
  - `allowed(role: Role, page: AccessKey, needed: Needed) -> bool`
  - `permissions_for(role: Role) -> dict[str, Level]` (all 14 pages plus `settings` and `access`)
- Produces: `RuntimeSettings.access: AccessSettings` (default factory `default_access`); `store.save(db, new, *, actor, expected_version, action: str = "settings.updated", audit_group: str | None = None)` (with `audit_group`, before/after hold only that group).

PageInfo labels/descriptions (shown on the admin page): Dashboard "Your own dashboard figures"; Complaint queue "View complaints, analysis and checks / log complaints, change status, re-run analysis"; Manual review "View the review queue / make reviewer decisions"; Enquiries "View the inbox / update or convert enquiries"; Mailbox "View received and sent e-mails / process an e-mail"; Orders "View orders and history / order actions"; Import complaints "View templates and imports / upload and import"; Analytics "Analytics and the organisation-wide dashboard"; Reports "View and export reports"; Knowledge base "View documents and passages / upload, activate, retire"; Taxonomy & SLAs "View categories, departments and SLAs / change them"; Rule matrix "View rules / edit rules"; Products "View products / edit products"; Users & roles "View the user list (changing roles is Administrator only)".

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_access_model.py`

```python
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


def test_defaults_match_today() -> None:
    d = access.default_access().model_dump()
    assert {k: (v["agent"], v["reviewer"], v["manager"]) for k, v in d.items()} == TODAY


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
    full = {k: dict(zip(access.EDITABLE_ROLES, v)) for k, v in TODAY.items()}
    assert access.validate_update(full).review.agent == "none"
    for bad in (
        {**full, "analytics": {**full["analytics"], "agent": "edit"}},
        {**full, "rules": {**full["rules"], "admin": "none"}},
        {k: v for k, v in full.items() if k != "rules"},
        {**full, "nope": full["rules"]},
    ):
        with pytest.raises(ValueError):
            access.validate_update(bad)
```

Add to `tests/integration/test_settings_api.py`:

```python
async def test_settings_save_keeps_the_access_matrix(
    client: httpx.AsyncClient,
    auth_headers: Callable[[Role], dict[str, str]],
    async_db: AsyncSession,
) -> None:
    admin_headers = auth_headers(Role.ADMIN)
    admin = (await async_db.scalars(select(User).where(User.role == Role.ADMIN))).one()
    changed = app_settings.load({"access": {"analytics": {"agent": "view"}}})
    await app_settings.save(
        async_db,
        changed,
        actor=admin,
        expected_version=None,
        action="access.updated",
        audit_group="access",
    )
    current = (await client.get(URL, headers=admin_headers)).json()
    saved = await client.put(
        URL, headers=admin_headers, json=body(current, email={"mailbox_check_seconds": 300})
    )
    assert saved.status_code == 200
    row = await app_settings.current_row(async_db)
    await async_db.refresh(row)
    stored = app_settings.load(row.data)
    assert stored.access.analytics.agent == "view"
    assert stored.email.mailbox_check_seconds == 300
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_access_model.py tests/integration/test_settings_api.py -q`
Expected: FAIL (`app_settings.access` does not exist).

- [ ] **Step 3: Implement** `app_settings/access.py` per the Interfaces block; add `access` to `RuntimeSettings` and `"access": default_access().model_dump()` to `defaults()`; add `action`/`audit_group` to `store.save`; export `access`, `AccessSettings`, `default_access` from `app_settings/__init__.py`; in `update_settings` pass `access=<current stored access>` when building `RuntimeSettings` (as it already does for logo keys). `level_for` imports `runtime` inside the function (module import cycle).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/unit/test_access_model.py tests/integration/test_settings_api.py tests/integration/test_app_settings_store.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy .` (all clean)

```bash
git add app_settings tests/unit/test_access_model.py tests/integration/test_settings_api.py src/api/routes/settings.py
git commit -m "feat(access): page catalogue and access matrix in run-time settings"
```

---

### Task 2: `require_access` and the "today's access" safety net

**Files:**
- Modify: `security/dependencies.py`
- Create: `tests/integration/test_page_access_gate.py`

**Interfaces:**
- Consumes: `app_settings.access.allowed`, `PageKey`, `Needed` (Task 1).
- Produces (in `security/dependencies.py`):
  - `NO_ACCESS = "You don't have access to this page"`
  - `require_access(page: PageKey, level: Needed) -> Callable[..., Awaitable[User]]` (depends on `get_current_user`; 403 `NO_ACCESS` when not allowed)
  - `ensure_access(user: User, page: PageKey, level: Needed) -> None` (raises the same 403; for staff branches of mixed endpoints)

- [ ] **Step 1: Write the parity test** in `tests/integration/test_page_access_gate.py`. It records today's access literally (not derived from the new code) and must pass both before and after Task 3.

```python
ALL = {"agent", "reviewer", "manager", "admin"}
INSIGHT = {"reviewer", "manager", "admin"}
MGR = {"manager", "admin"}
ADMIN = {"admin"}
ID = "00000000-0000-0000-0000-000000000001"
ROUTES = [  # (method, path under /api/v1, roles allowed today)
    ("GET", "/dashboard/agent", ALL),
    ("GET", "/complaints/CMP-999999/analysis", ALL),
    ("POST", "/complaints/CMP-999999/analyze", ALL),
    ("GET", "/complaints/CMP-999999/validation", ALL),
    ("POST", "/complaints/CMP-999999/validate", ALL),
    ("GET", "/complaints/CMP-999999/decisions", ALL),
    ("PATCH", "/complaints/CMP-999999/status", ALL),
    ("GET", "/complaints/CMP-999999/chat", ALL),
    ("GET", "/review-queue", INSIGHT),
    ("POST", "/complaints/CMP-999999/review", INSIGHT),
    ("GET", "/enquiries", ALL),
    ("PATCH", "/enquiries/ENQ-999999", ALL),
    ("POST", "/enquiries/ENQ-999999/convert", ALL),
    ("GET", "/mailbox", ALL),
    ("GET", "/mailbox/inbound", ALL),
    ("GET", "/mailbox/outbound", ALL),
    ("POST", "/mailbox/process", ALL),
    ("GET", "/admin/orders", ALL),
    ("GET", "/admin/orders/ORD-999999", ALL),
    ("POST", "/admin/orders/ORD-999999/actions", ALL),
    ("GET", "/imports", MGR),
    ("GET", f"/imports/{ID}", MGR),
    ("GET", f"/imports/{ID}/result.csv", MGR),
    ("GET", "/imports/template.csv", MGR),
    ("GET", "/imports/template.xlsx", MGR),
    ("POST", "/imports/preview", MGR),
    ("POST", f"/imports/{ID}/run", MGR),
    ("GET", "/analytics", INSIGHT),
    ("GET", "/dashboard/admin", INSIGHT),
    ("GET", "/reports", INSIGHT),
    ("GET", "/reports/x", INSIGHT),
    ("GET", "/reports/x/export", INSIGHT),
    ("GET", "/documents", ALL),
    ("GET", "/documents/types", ALL),
    ("GET", f"/documents/{ID}", ALL),
    ("GET", f"/document-versions/{ID}/file", ALL),
    ("GET", f"/document-versions/{ID}/chunks", ALL),
    ("GET", "/knowledge-base/search?q=late", ALL),
    ("POST", "/documents/upload", ADMIN),
    ("POST", f"/document-versions/{ID}/activate", ADMIN),
    ("POST", f"/document-versions/{ID}/retire", ADMIN),
    ("POST", f"/document-versions/{ID}/reprocess", ADMIN),
    ("GET", "/taxonomy/sla-policies", ALL),
    ("POST", "/taxonomy/departments", ADMIN),
    ("PATCH", f"/taxonomy/departments/{ID}", ADMIN),
    ("POST", "/taxonomy/categories", ADMIN),
    ("PATCH", f"/taxonomy/categories/{ID}", ADMIN),
    ("POST", f"/taxonomy/categories/{ID}/subcategories", ADMIN),
    ("PATCH", f"/taxonomy/sla-policies/{ID}", ADMIN),
    ("GET", "/rules", ALL),
    ("GET", "/rules/facts", ALL),
    ("GET", "/rules/export.csv", ALL),
    ("POST", "/rules", ADMIN),
    ("PUT", "/rules/DEL-001", ADMIN),
    ("GET", "/admin/products", ADMIN),
    ("POST", "/admin/products", ADMIN),
    ("PATCH", "/admin/products/VH-NONE", ADMIN),
    ("POST", "/admin/products/VH-NONE/images", ADMIN),
    ("PUT", "/admin/products/VH-NONE/images/order", ADMIN),
    ("DELETE", f"/admin/products/VH-NONE/images/{ID}", ADMIN),
    ("GET", "/users", MGR),
    ("PATCH", f"/users/{ID}", ADMIN),
    ("GET", "/settings", ADMIN),
    ("PUT", "/settings", ADMIN),
    ("GET", "/taxonomy/departments", ALL | {"customer"}),
    ("GET", "/taxonomy/categories", ALL | {"customer"}),
    ("GET", "/taxonomy/vocabulary", ALL),
]


@pytest.mark.parametrize("method,path,allowed", ROUTES)
@pytest.mark.parametrize("role", ["customer", "agent", "reviewer", "manager", "admin"])
async def test_default_access_matches_today(client, auth_headers, role, method, path, allowed):
    r = await client.request(
        method,
        "/api/v1" + path,
        headers=auth_headers(Role(role)),
        json={} if method in ("POST", "PUT", "PATCH") else None,
    )
    assert (r.status_code != 403) == (role in allowed), (role, method, path, r.status_code)
```

Plus unit-level tests of the new dependency with a minimal app (`FastAPI()` with one route using `require_access("rules", "edit")`, `get_current_user` overridden): manager → 403 with detail `NO_ACCESS`; admin → 200; and `ensure_access` raises 403 for an agent on `"imports"`.

- [ ] **Step 2: Run** `uv run pytest tests/integration/test_page_access_gate.py -q`
Expected: parity rows PASS already (they describe today); the `require_access`/`ensure_access` tests FAIL (not defined). If any parity row fails now, fix the row to match today's behaviour (the inventory is the source of truth), not the code.

- [ ] **Step 3: Implement** `NO_ACCESS`, `require_access`, `ensure_access` in `security/dependencies.py`.

- [ ] **Step 4: Run** the file again. Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
git add security/dependencies.py tests/integration/test_page_access_gate.py
git commit -m "feat(access): require_access dependency and today's-access parity test"
```

---

### Task 3: Gate every staff route with the matrix

**Files:**
- Modify: `src/api/routes/analytics.py`, `complaints.py`, `review.py`, `chat.py`, `attachments.py`, `contact.py`, `mailbox.py`, `orders.py`, `imports.py`, `documents.py`, `taxonomy.py`, `rules.py`, `storefront.py` (admin products only), `users.py` (`GET /users` only)
- Test: `tests/integration/test_page_access_gate.py` (new tests)

**Interfaces:**
- Consumes: `require_access`, `ensure_access`, `NO_ACCESS` (Task 2); `app_settings.override` / `load` for tests.

Mapping: follow the spec section 1 table exactly (view endpoints → `require_access(page, "view")`, edit endpoints → `require_access(page, "edit")`). Keep `require_roles(Role.ADMIN)` on the locked endpoints (settings, logos, `PATCH /users/{id}`) and `get_current_user` on shared lookups. In mixed endpoints (`GET/POST /complaints`, `GET /complaints/{ref}`, attachments, `GET /orders/{ref}/events`, `GET /orders/{ref}/receipt.pdf`), call `ensure_access(user, page, level)` **first thing** in the handler when `user.role` is a staff role, before any lookup (so a denied user never learns whether a record exists).

- [ ] **Step 1: Write the failing tests** (add to `tests/integration/test_page_access_gate.py`):

```python
def matrix(**pages):  # e.g. matrix(analytics={"agent": "view"})
    return app_settings.load({"access": pages})


async def test_matrix_grants_and_removes(client, auth_headers):
    agent = auth_headers(Role.AGENT)
    app_settings.override(matrix(analytics={"agent": "view"}, rules={"agent": "none"}))
    assert (await client.get("/api/v1/analytics", headers=agent)).status_code == 200
    r = await client.get("/api/v1/rules", headers=agent)
    assert r.status_code == 403 and r.json()["detail"] == NO_ACCESS


async def test_view_is_not_edit(client, auth_headers):
    app_settings.override(matrix(orders={"agent": "view"}))
    agent = auth_headers(Role.AGENT)
    assert (await client.get("/api/v1/admin/orders", headers=agent)).status_code == 200
    assert (
        await client.post("/api/v1/admin/orders/ORD-1/actions", headers=agent, json={})
    ).status_code == 403


async def test_admin_cannot_be_locked_out_and_customer_cannot_be_let_in(client, auth_headers):
    app_settings.override(
        matrix(**{k: {"agent": "none", "reviewer": "none", "manager": "none"} for k in PAGE_KEYS})
    )
    assert (await client.get("/api/v1/rules", headers=auth_headers(Role.ADMIN))).status_code == 200
    assert (
        await client.get("/api/v1/rules", headers=auth_headers(Role.CUSTOMER))
    ).status_code == 403


async def test_mixed_endpoints_gate_only_staff(client, auth_headers):
    app_settings.override(matrix(complaints={"agent": "none"}))
    assert (
        await client.get("/api/v1/complaints", headers=auth_headers(Role.AGENT))
    ).status_code == 403
    assert (
        await client.get("/api/v1/complaints", headers=auth_headers(Role.CUSTOMER))
    ).status_code == 200
    assert (
        await client.get("/api/v1/complaints/CMP-999999", headers=auth_headers(Role.AGENT))
    ).status_code == 403


async def test_shared_lookups_stay_open(client, auth_headers):
    app_settings.override(matrix(taxonomy={"agent": "none"}))
    for p in ("/taxonomy/departments", "/taxonomy/categories", "/taxonomy/vocabulary"):
        assert (
            await client.get("/api/v1" + p, headers=auth_headers(Role.AGENT))
        ).status_code == 200


def test_every_staff_route_is_gated():
    """Route inventory: any route using require_roles must be admin-locked; staff routes use require_access."""
    # walk create_app() routes (including included routers); for each APIRoute collect the
    # dependency callables; fail if a route uses a require_roles closure whose role set is not
    # exactly {ADMIN} or {CUSTOMER}. Allowlist: none needed after this task.
```

(`app_settings.override(...)` is reset by the autouse fixture in `tests/conftest.py`.)

- [ ] **Step 2: Run** `uv run pytest tests/integration/test_page_access_gate.py -q`
Expected: the new tests FAIL; the Task 2 parity rows still PASS.

- [ ] **Step 3: Replace the guards** route module by route module per the mapping; remove now-unused `staff`/`insight_roles`/`managers`/`reviewers` names.

- [ ] **Step 4: Run** `uv run pytest -q` (whole suite)
Expected: PASS, including every parity row (defaults reproduce today).

- [ ] **Step 5: Lint and commit**

```bash
git add src/api/routes tests/integration/test_page_access_gate.py
git commit -m "feat(access): staff routes follow the page access matrix"
```

---

### Task 4: Access API and permissions in `/me`

**Files:**
- Create: `src/api/routes/access.py`
- Modify: `src/main.py` (include router under `/api/v1`), `src/api/schemas.py` (`MeOut`, `AccessPageOut`, `AccessOut`, `AccessUpdate`), `src/api/routes/users.py` (`/me` returns `MeOut`)
- Test: `tests/integration/test_access_api.py`

**Interfaces:**
- Consumes: Task 1 (`PAGES`, `validate_update`, `permissions_for`, `store.save(..., action="access.updated", audit_group="access")`, `StaleSettingsError`).
- Produces:
  - `MeOut(UserOut)`: `permissions: dict[str, Literal["none","view","edit"]]`
  - `AccessPageOut`: `key, label, description, has_edit, default: PageAccess`
  - `AccessOut`: `pages: list[AccessPageOut], matrix: AccessSettings, version: int, updated_at: datetime | None, updated_by: str | None`
  - `AccessUpdate`: `matrix: dict[str, dict[str, str]], version: int`
  - `GET /api/v1/access` → `AccessOut` (admin only); `PUT /api/v1/access` → `AccessOut`; 409 detail `"Someone else changed the settings; reload and try again."` (same text as `PUT /settings`); 422 with the `ValueError` message.

- [ ] **Step 1: Write the failing tests** in `tests/integration/test_access_api.py`:
  - `test_admin_reads_catalogue_and_matrix`: 14 pages in spec order, `has_edit` false for `dashboard/analytics/reports/users`, `version == 0`.
  - `test_put_applies_immediately`: admin PUTs a full matrix with `analytics.agent = "view"`; the very next `GET /api/v1/analytics` as an agent → 200 (cache cleared by `save`); `/me` for that agent shows `permissions["analytics"] == "view"`.
  - `test_put_is_audited`: an `audit_events` row with action `access.updated` whose before/after contain only the access group.
  - `test_stale_put_409` (second PUT with the old version) and `test_invalid_put_422` (missing page; `edit` on `reports`; extra `admin` key).
  - `test_non_admins_get_403` on GET and PUT for agent, reviewer, manager, customer.
  - `test_put_keeps_other_settings`: change `email.mailbox_check_seconds` via `PUT /settings`, then `PUT /access`; the e-mail value is unchanged.
  - `test_me_permissions_per_role`: admin all `edit` incl. `settings`/`access`; customer all `none`; reviewer `review == "edit"`, `imports == "none"`.

- [ ] **Step 2: Run** `uv run pytest tests/integration/test_access_api.py -q` → FAIL (404 on `/access`).

- [ ] **Step 3: Implement** the schemas, the router (build the new `RuntimeSettings` from the stored row with only `access` replaced, then `save(..., action="access.updated", audit_group="access")`), register it in `src/main.py`, and make `/me` return `MeOut(**UserOut fields, permissions=permissions_for(user.role))`.

- [ ] **Step 4: Run** `uv run pytest -q` → PASS. Then `make openapi` (regenerates `web/src/lib/api/generated`).

- [ ] **Step 5: Lint and commit**

```bash
git add src tests/integration/test_access_api.py web/src/lib/api/generated
git commit -m "feat(access): admin access API and permissions on /me"
```

---

### Task 5: Website follows permissions (menu, page guards, edit buttons, dashboard)

**Files:**
- Create: `web/src/lib/access.ts`, `web/src/components/no-access.tsx`
- Modify: `web/src/components/app-sidebar.tsx`; the staff pages under `web/src/app/(app)/` (`dashboard`, `complaints`, `complaints/[ref]`, `complaints/new`, `review`, `enquiries`, `mailbox`, `fulfilment`, `imports`, `analytics`, `reports`, `knowledge-base`, `settings/taxonomy`, `settings/rules`, `settings/products`, `settings/users`); edit controls in `components/complaints/complaint-view.tsx` (Re-run analysis), `status-control.tsx`, `review-panel.tsx`, `components/fulfilment/orders-manager.tsx` (action buttons), enquiries actions, mailbox "Process an e-mail", imports upload, knowledge base / taxonomy / rules (`canManage`/`canEdit` now from `can(..., "edit")`)
- `settings/general` and `settings/users` role editing keep `role === "admin"` (locked).

**Interfaces:**
- Consumes: generated `MeOut` (`permissions`) from Task 4.
- Produces:
  - `web/src/lib/access.ts`: `export type Level = "none" | "view" | "edit"`; `export type AccessKey = "dashboard" | ... | "users" | "settings" | "access"`; `export function can(user: { permissions: Record<string, Level> }, key: AccessKey, level: "view" | "edit" = "view"): boolean`.
  - `NoAccess` component: a centered panel, heading "You don't have access to this page", text "Ask an administrator.", button "Back to dashboard" (`/dashboard`). On `/dashboard` itself the button is omitted.
  - Sidebar `NavItem`: `{ title, href, icon, page: AccessKey } | { title, href, icon, customer: true }`; staff items show when `can(user, page)`; customer items when `user.role === "customer"`. `getCurrentUser()` returns `MeOut`.
  - Dashboard: customer branch unchanged; staff without `dashboard` view → `NoAccess`; with `can(user, "analytics")` → `AdminDashboard`, else `AgentDashboard`.

- [ ] **Step 1: Implement** `access.ts`, `NoAccess`, the sidebar change, then each page guard (`if (!can(user, "<page>")) return <NoAccess />` replacing the role `redirect`s; complaint pages apply it only for staff) and the edit controls.

- [ ] **Step 2: Verify the build**

Run: `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build`
Expected: no errors. Also `grep -rnE "role (===|!==) \"(agent|reviewer|manager)\"|\\[\"reviewer\", \"manager\", \"admin\"\\]" web/src` returns nothing outside `lib/roles.ts`.

- [ ] **Step 3: Browser check** (API on 8000, web dev server, admin + agent test accounts):
  1. Defaults: agent sidebar = Dashboard, Complaint queue, Enquiries, Mailbox, Orders, Knowledge base, Taxonomy & SLAs, Rule matrix (same as before); agent dashboard renders.
  2. Store `analytics.agent = "view"` (via `PUT /api/v1/access` as admin, or Task 6 page once built); after ≤15 s and a reload the agent sees Analytics and it loads, and Dashboard shows the organisation-wide view.
  3. `orders.agent = "view"`: Orders loads with no action buttons. `complaints.agent = "view"`: a complaint opens; status control, Re-run analysis and review panel are hidden.
  4. `dashboard.agent = "none"`: signing in lands on the no-access panel without a redirect loop; groups with no visible items are hidden.
  5. Typing `/analytics` with `none` shows the no-access panel.
  Restore defaults afterwards.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(web): menu, pages and edit buttons follow page access"
```

---

### Task 6: The Page access admin page

**Files:**
- Create: `web/src/app/(app)/settings/access/page.tsx`, `web/src/components/settings/access-manager.tsx`
- Modify: `web/src/components/app-sidebar.tsx` (item "Page access", icon `ShieldCheck`, `page: "access"`, after Users & roles)

**Interfaces:**
- Consumes: generated `getAccess`/`putAccess` (query/mutation options from Task 4's `make openapi`), `can()` from Task 5.

Behaviour (spec section 4): page title "Page access", description "Choose which staff roles can view or change each page. Administrators always have full access."; non-admins get `NoAccess`. Table: rows = `pages` (label + description), column groups Support Agent / Reviewer / Support Manager / Administrator, each with View and Edit checkboxes (no Edit checkbox where `has_edit` is false); Administrator column all checked and disabled with a lock icon and tooltip "Administrators always have full access". Ticking Edit ticks View; unticking View unticks Edit. Changed rows show a dot. Below the table: "Always Administrator only: Settings, Page access, changing a user's role." Buttons: Save (disabled until changed; on success toast "Saved. Applies within 15 seconds" and refetch), Discard, Reset to defaults (confirm dialog; sets each page to `default`, saved only on Save). 409 → toast "Someone else changed the settings. Reload to see their changes." `beforeunload` warning while there are unsaved changes.

- [ ] **Step 1: Implement** the page and `AccessManager`, following `components/settings/settings-manager.tsx` for loading, saving and toasts.

- [ ] **Step 2: Verify the build** — `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` → clean.

- [ ] **Step 3: Browser check:** as admin, tick Analytics → View for Support Agent and save (toast shows); as agent, reload after ≤15 s: Analytics appears and loads. Untick and save: it disappears and `/analytics` shows the no-access panel. Reset to defaults + Save restores the original matrix. Open the page in two tabs, save in one, save in the other → conflict toast. Sign in as manager: no Page access in the menu; `/settings/access` shows the no-access panel.

- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(web): Page access admin page"
```

---

### Task 7: Documentation and full check

**Files:**
- Modify: `documentation/user_guide.md` (a "Page access" section: where it is, what View and Edit mean, locked pages, 15-second delay), `documentation/evaluator_guide.md` (section 5 table row: "Give a role access to a page | Page access → tick View/Edit for the role → Save | Database (no code)"), `documentation/project_report.md` (section 7 Administration row: mention page access)

- [ ] **Step 1: Write the doc changes.**
- [ ] **Step 2: Full check** — `make lint && make test` (backend: all pass, test count above 526) and `pnpm --dir web build` (clean).
- [ ] **Step 3: Commit**

```bash
git add documentation
git commit -m "docs: page access in the user and evaluator guides"
```
