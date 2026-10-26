# Page access: administrators choose which roles can view or edit each staff page

Date: 2026-10-26. Status: design approved in conversation, awaiting spec review.

## Goal

An administrator can change, from a page in the app, which staff roles may **view** and which
may **edit** each page of the staff console. The API enforces it (not only the menu), changes
apply within 15 seconds without a redeploy, and every change is audited.

## Decisions (from the conversation)

- Granularity: **page + edit** (a View and an Edit switch per page and role).
- Applies **per role** (Support Agent, Reviewer, Support Manager). No per-person exceptions.
- Storage: approach A, the existing run-time settings (`app_settings`), not a new table.
- Administrators always have full access; Settings, Page access and changing a user's role
  stay **Administrator only** and are not in the matrix.
- Customers and customer/public pages are not part of the matrix.

## 1. Pages, endpoints and defaults

Levels: `none` < `view` < `edit` (edit includes view). Pages without edit actions accept
only `none` or `view`; a stored `edit` for them is read as `view`. The defaults reproduce
today's access exactly.

| Page key | Sidebar item | View endpoints | Edit endpoints | Default agent / reviewer / manager |
|---|---|---|---|---|
| `dashboard` | Dashboard | `GET /dashboard/agent` | (none) | view / view / view |
| `complaints` | Complaint queue | staff branch of `GET /complaints`, `GET /complaints/{ref}`; `GET /complaints/{ref}/analysis`, `/validation`, `/decisions`, `/chat`; staff branch of attachment reads | staff branch of `POST /complaints` (log for a customer); `POST /complaints/{ref}/analyze`, `/validate`; `PATCH /complaints/{ref}/status`; staff branch of attachment upload/delete | edit / edit / edit |
| `review` | Manual review | `GET /review-queue` | `POST /complaints/{ref}/review` | none / edit / edit |
| `enquiries` | Enquiries | `GET /enquiries` | `PATCH /enquiries/{ref}`, `POST /enquiries/{ref}/convert` | edit / edit / edit |
| `mailbox` | Mailbox | `GET /mailbox`, `/mailbox/inbound`, `/mailbox/outbound` | `POST /mailbox/process` | edit / edit / edit |
| `orders` | Orders | `GET /admin/orders`, `/admin/orders/{ref}`; staff branch of `GET /orders/{ref}/events`, `/orders/{ref}/receipt.pdf` | `POST /admin/orders/{ref}/actions` | edit / edit / edit |
| `imports` | Import complaints | `GET /imports`, `/imports/{id}`, `/imports/{id}/result.csv`, templates | `POST /imports/preview`, `POST /imports/{id}/run` | none / none / edit |
| `analytics` | Analytics | `GET /analytics`, `GET /dashboard/admin` | (none) | none / view / view |
| `reports` | Reports | `GET /reports`, `/reports/{code}`, `/reports/{code}/export` | (none) | none / view / view |
| `knowledge_base` | Knowledge base | `GET /documents`, `/documents/types`, `/documents/{id}`, `/document-versions/{id}/file`, `/document-versions/{id}/chunks`, `/knowledge-base/search` | `POST /documents/upload`, `/document-versions/{id}/activate`, `/retire`, `/reprocess` | view / view / view |
| `taxonomy` | Taxonomy & SLAs | `GET /taxonomy/sla-policies` | `POST`/`PATCH` departments, categories, subcategories; `PATCH /taxonomy/sla-policies/{id}` | view / view / view |
| `rules` | Rule matrix | `GET /rules`, `/rules/facts`, `/rules/export.csv` | `POST /rules`, `PUT /rules/{id}` | view / view / view |
| `products` | Products | `GET /admin/products` | `POST`/`PATCH /admin/products...`, image upload, order and delete | none / none / none |
| `users` | Users & roles | `GET /users` | (none: role changes are locked, section 2) | none / none / view |

Paths are under `/api/v1`. **Shared lookups stay open to every signed-in staff member and are
not gated by any page**, because several pages use them: `GET /taxonomy/departments`,
`GET /taxonomy/categories`, `GET /taxonomy/vocabulary`, `GET /me`. Customer and public
endpoints (shop, checkout, chat, contact, My orders, the customer branch of complaint and
order endpoints) are unchanged.

"Staff branch" means: the endpoint already serves customers (their own records) and staff;
only the staff path checks the page. The customer path keeps its ownership rules.

## 2. Locked rules

1. Administrators: the API never consults the matrix; every page is `edit`. The admin column
   is shown ticked and disabled.
2. Administrator only, not in the matrix: `GET/PUT /settings`, logo upload/delete, the new
   `GET/PUT /access`, and `PATCH /users/{id}` (changing a role).
3. Customers never pass a page check, whatever is stored (`role == customer` → 403 before the
   matrix is read).
4. Missing or invalid stored data for a page falls back to that page's default; unknown page
   keys or roles in storage are ignored. One bad entry never resets other pages or other
   settings.
5. Denied requests get **403** with `"You don't have access to this page"`.

## 3. Storage and server code

- `app_settings/model.py`: new group `AccessSettings` on `RuntimeSettings` with one field per
  page key, each a `PageAccess {agent, reviewer, manager}` of level strings. A field validator
  coerces invalid values per page to the default (rule 2.4) and `edit` to `view` for pages
  without edit endpoints. Defaults live in `app_settings/defaults.py`.
- `app_settings/access.py` (new): the page catalogue (key, label, description, has_edit) and
  `level_for(role, page) -> Level` / `allowed(role, page, needed) -> bool`, reading
  `runtime().access`. Pure functions, used by the API and by `/me`. `runtime()` is the same
  cached read the other settings use (at most one database read per 15 seconds per process).
- `security/dependencies.py`: `require_access(page, level)` dependency (403 per section 2) and
  `ensure_access(user, page, level)` for staff branches inside mixed endpoints. Route modules
  replace `require_roles(...)` with these per the table; `require_roles(Role.ADMIN)` stays for
  the locked endpoints.
- Saving: both the Settings page and the Page access page use the existing `store.save` with
  the shared `version` (stale save → 409). `PUT /settings` keeps the stored `access` group
  unchanged; `PUT /access` changes only the `access` group. Audit actions:
  `settings.updated` (unchanged) and `access.updated` (before/after of the matrix).
- API (admin only):
  - `GET /api/v1/access` → `{pages: [{key, label, description, has_edit, default}], matrix,
    version, updated_at, updated_by}`.
  - `PUT /api/v1/access` body `{matrix, version}` → 200 with the new state; 409 when stale;
    422 for unknown pages/roles/levels, `admin`/`customer` keys, or `edit` on a page without
    edit.
- `GET /me` adds `permissions: {page_key: "none" | "view" | "edit"}` for every matrix page,
  plus `settings` and `access` (`edit` for administrators, `none` otherwise). Customers get
  `none` everywhere.

## 4. Website

- New page `/settings/access` ("Page access"), sidebar item under Administration after Users &
  roles, administrators only. A table of pages × roles with View and Edit checkboxes (edit
  ticks view, unticking view unticks edit; pages without edit show View only); admin column
  disabled with a lock and tooltip; a note listing the locked pages; Save (disabled until
  changed; toast "Saved. Applies within 15 seconds"), Discard, Reset to defaults (confirm;
  applies on Save); changed rows marked; leave-page warning with unsaved changes; 409 shows
  "Someone else changed the settings. Reload to see their changes."
- `web/src/lib/access.ts`: `can(user, page, level)` from `user.permissions`.
- Sidebar: items carry a page key instead of a role list and show when `can(view)`.
- Page guards: each staff page's server check uses `can(...)`; without access it renders a
  "You don't have access to this page. Ask an administrator." panel with a link to the
  dashboard (instead of a silent redirect).
- Edit controls use `can(edit)` instead of role checks (`canManage`/`canEdit` props in
  knowledge base, taxonomy, rules, orders actions, review panel, complaint status and re-run,
  enquiries, mailbox process, imports).
- Dashboard: the organisation-wide dashboard shows when `can(analytics, view)`, otherwise
  the agent dashboard (same result as today with the defaults).
- `make openapi` regenerates the client for `/access` and `permissions`.

## 5. Error handling

- Settings unreadable → defaults (today's access), logged, as for other settings.
- Stale save → 409; invalid matrix → 422 with the field; non-admin → 403.
- Permission changes reach other API instances within the 15-second cache; the browser
  reflects them on the next navigation or reload.

## 6. Tests

- Defaults: a table-driven test walks every staff endpoint in section 1 for agent, reviewer,
  manager, admin and customer and asserts the same allow/deny as before this change.
- Gate: per page, `none` → 403 on view endpoints; `view` → 403 on edit endpoints and 200 on
  view; `edit` → 200; admins pass with a matrix that tries to remove them; customers get 403
  even if storage lists them; shared lookups stay open to all staff.
- Mixed endpoints: customer path unchanged; staff path follows the matrix.
- Storage: invalid page entry falls back to its default without touching others; unknown keys
  ignored; `edit` on a view-only page read as `view`.
- Saving: `PUT /access` 200/409/422/403; audit `access.updated`; `PUT /settings` keeps
  `access`; `PUT /access` keeps other groups.
- `/me` permissions for each role before and after a change.
- Web: type check, lint, production build; browser check: grant agent Analytics, sign in as
  agent, page appears and loads; remove it, sidebar hides it and the URL shows the no-access
  panel.

## 7. Documentation

User guide and study guide: a "Page access" section. Evaluator guide "live modification
tasks": *Give a role access to a page → Page access*.

## Out of scope

Per-person exceptions; new custom roles; customer/public pages; field-level hiding inside a
page; pushing permission changes to an already-open page without navigation.
