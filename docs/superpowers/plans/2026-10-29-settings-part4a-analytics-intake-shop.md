# Settings Part 4a (Analytics, intake, shop) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trend/dashboard/SLA-status values, intake, duplicate, chat and import limits, and the shop's socials, FAQ, best-seller window and delayed-order wait become admin settings on new Analytics, Intake and Shop tabs (plus the Orders tab).

**Architecture:** Three new groups (`analytics`, `intake`, `shop`) and one `orders` field in the run-time settings, saved through the existing `PUT /settings` (optional groups). Every reader switches from module constants / YAML to `app_settings.runtime()`; the storefront config endpoint and the chat take socials and FAQ from the settings.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2, pytest; Next.js 16, TanStack Query, generated @hey-api client (`make openapi`).

**Spec:** `docs/superpowers/specs/2026-10-29-settings-part4a-analytics-intake-shop-design.md`

## Global Constraints

- Field names, defaults and limits exactly as spec §1 (analytics: `trend_window_days` 7 [1–90], `trend_min_count` 3 [1–100], `trend_rise_ratio` 1.5 [1.0–10.0], `recurring_min_count` 3 [1–100], `watched_categories` [DELIVERY, BILLING] 0–20 unique, `dashboard_list_limit` 10 [5–50], `first_response_statuses` / `resolved_statuses` 1–9 unique `ComplaintStatus` values; intake: `near_duplicate_min_ratio` 88 [70–100], `related_min_similarity` 0.80 [0.50–0.99], `duplicate_window_days` 30 [1–365], `repeat_window_days` 60 [1–365], `repeat_min_gap_hours` 24 [0–168], `min_title_chars` 5 [3–20], `min_description_chars` 20 [10–200], `min_description_words` 5 [1–30], `max_description_chars` 5000 [500–5000, > min], `max_attachments` 5 [0–10], `max_attachment_mb` 5 [1–10], `chat_max_questions` 6 [2–12], `chat_max_message_chars` 2000 [200–2000], `chat_max_customer_messages` 30 [5–100], `import_max_rows` 1000 [10–5000]; shop: `best_seller_days` 90 [7–365], `socials` 0–8 `{name 1–30, url https:// ≤200}`, `faq` 1–20 `{question 5–200, answer 10–1000}`; orders: `delay_wait_steps` 3 [1–20]).
- FAQ placeholders = keys of `storefront.yaml` `shipping` + `returns` + `warranty`. Error texts: `FAQ <n>: unknown placeholder {<name>}; use one of {a}, {b}, …` and `FAQ <n>: braces must wrap a placeholder name` (broken braces). `Watched categories: category <CODE> does not exist.`
- `PUT /settings`: `analytics`, `intake`, `shop` optional (left out = keep stored); `orders.delay_wait_steps` optional in the payload (missing = default). `SettingsOut` adds `complaint_statuses: list[str]` and `policy_values: dict[str, int]`.
- Limit messages quote the current value (e.g. "Description must be at most 100 characters.").
- Commit after each task, no `Co-Authored-By` line. Never commit `documentation/architecture.drawio`.

## Review Focus

1. A stored limit that no longer validates (e.g. a min raised above a max by a later default change) falls back to the group's defaults, never breaks intake — Task 1 `test_bad_intake_group_resets_only_that_group`.
2. An FAQ answer with a literal brace pair like `{ }` or `{0}` must be refused, not crash `str.format` at request time — Task 1 `test_faq_braces_refused`.
3. Settings older clients send without the new groups keep the stored values (no silent reset to defaults) — Task 2 `test_new_groups_left_out_keep_stored`.
4. Attachment uploads read only `max_attachment_mb` + 1 byte, so a bigger file is refused without reading it whole — Task 3 `test_attachment_size_from_settings`.
5. The chat's FAQ answers and the shop's FAQ show the same saved text — Task 4 `test_chat_faq_uses_settings`.

---

### Task 1: Settings model and defaults

**Files:**
- Modify: `app_settings/model.py`, `app_settings/defaults.py`
- Create: `storefront/faq.py`
- Test: `tests/unit/test_part4a_settings.py`

**Interfaces:**
- Produces: `AnalyticsSettings`, `IntakeSettings`, `SocialLink(name, url)`, `FaqEntrySetting(question, answer)`, `ShopSettings`, `OrderSettings.delay_wait_steps: int = 3`; `RuntimeSettings.analytics/intake/shop`. `storefront.faq.policy_values() -> dict[str, int]` (from `storefront_config()` shipping/returns/warranty); `storefront.faq.placeholder_problem(text: str) -> str | None` (uses `string.Formatter().parse`); `storefront.faq.filled(answer: str) -> str`.

- [ ] **Step 1: Write the failing tests:**
  - `test_defaults_equal_today`: analytics (7, 3, 1.5, 3, ["DELIVERY", "BILLING"], 10, the 5 first-response statuses, ["resolved", "closed"]); intake (88, 0.80, 30, 60, 24, 5, 20, 5, 5000, 5, 5, 6, 2000, 30, 1000); shop (90, socials names ["Instagram", "X", "YouTube"], 7 FAQ items, first answer contains `{standard_days}`); `orders.delay_wait_steps == 3`.
  - `test_limits_refused` (parametrized, one bad value per field at each bound in Global Constraints, plus: `first_response_statuses` []; `resolved_statuses` ["done"]; duplicate watched category; social url `http://x.com`; 9 socials; 0 and 21 FAQ items).
  - `test_faq_braces_refused`: answers `"in {foo} days"`, `"a { } b"`, `"a {0} b"`, `"a { b"` each refused; `"within {standard_days} days"` accepted; message contains `FAQ 1: unknown placeholder {foo}`.
  - `test_filled`: `filled("{standard_days} days") == "5 days"`.
  - `test_bad_intake_group_resets_only_that_group`: `load({"intake": {"min_description_chars": 200, "max_description_chars": 150}, "email": {"mailbox_check_seconds": 120}})` → intake equals defaults, email 120.
- [ ] **Step 2: Run** `uv run pytest tests/unit/test_part4a_settings.py -q` — Expected: FAIL (imports).
- [ ] **Step 3: Implement.** No separate max-above-min check: the ranges (min ≤ 200, max ≥ 500) already guarantee it. Status values from `database.models.ComplaintStatus` (local import in the validator). Defaults: analytics from `analytics_config()`, intake as literals in `defaults.py`, shop socials/FAQ from `storefront.yaml` raw (unformatted FAQ), `delay_wait_steps` 3.
- [ ] **Step 4: Run** the new tests and `uv run pytest tests/unit -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(settings): analytics, intake and shop groups`.

### Task 2: Saving and reading the new groups

**Files:**
- Modify: `src/api/schemas.py`, `src/api/routes/settings.py`, `web/openapi.json` + generated client (`make openapi`), `web/src/components/settings/settings-manager.tsx` (Form passes the new groups through unchanged)
- Test: `tests/integration/test_settings_api.py`

**Interfaces:**
- Consumes: Task 1 models, `policy_values()`.
- Produces: `SettingsUpdate.analytics/intake/shop` optional; `SettingsOut.complaint_statuses`, `SettingsOut.policy_values`.

- [ ] **Step 1: Write the failing tests:** `body()` helper includes the three groups; `test_watched_category_must_exist` (FOO → 422 exact text); `test_new_groups_left_out_keep_stored` (save intake change, then save without `intake` → kept); `test_settings_lists_statuses_and_policy_values` (`"closed" in complaint_statuses`, `policy_values["standard_days"] == 5`); `test_delay_wait_steps_optional` (orders without the field → 200, value 3).
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_settings_api.py -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** (`payload.x or stored.x`; taxonomy check as Part 2's `_check_validation_codes`); `make openapi`; settings-manager `toForm` includes `analytics`, `intake`, `shop`.
- [ ] **Step 4: Run** `make lint && uv run pytest tests/integration/test_settings_api.py -q` and `pnpm --dir web typecheck` — Expected: clean, PASS.
- [ ] **Step 5: Commit** `feat(settings): save analytics, intake and shop settings`.

### Task 3: Intake, duplicate, chat, attachment and import readers

**Files:**
- Modify: `complaint_processing/duplicates.py`, `complaint_processing/service.py`, `complaint_processing/facts.py`, `complaint_processing/attachments.py`, `src/api/routes/attachments.py`, `src/api/routes/mailbox.py`, `support_chat/intake.py`, `support_chat/service.py`, `support_contact/service.py`, `email_channel/inbound.py`, `bulk_import/reader.py`, `tests/unit/test_chat_intake.py` (use the settings value instead of `MAX_QUESTIONS`)
- Test: `tests/unit/test_intake_settings.py`, `tests/integration/test_intake_settings_api.py`

**Interfaces:**
- Consumes: `app_settings.runtime().intake`.
- Produces: no new public names; constants `MIN_TITLE_CHARS`, `MIN_DESCRIPTION_CHARS`, `MIN_DESCRIPTION_WORDS`, `MAX_DESCRIPTION_CHARS`, `DUPLICATE_WINDOW_DAYS`, `NEAR_DUPLICATE_MIN_RATIO`, `RELATED_MIN_SIMILARITY`, `REPEAT_WINDOW_DAYS`, `REPEAT_MIN_GAP_HOURS`, `MAX_ATTACHMENT_BYTES`, `MAX_ATTACHMENTS`, `MAX_QUESTIONS`, `MAX_MESSAGE_CHARS`, `MAX_CUSTOMER_MESSAGES`, `MAX_ROWS` are removed.

- [ ] **Step 1: Write the failing tests** (unit tests override settings like Part 2's `_with_validation`; integration tests save through `PUT /settings` then `app_settings.reset_cache()`):
  - `test_description_max_from_settings`: max 100 → a 150-character description gives issue "Description must be at most 100 characters."
  - `test_title_min_from_settings`: min 10 → "Title must be at least 10 characters."
  - `test_near_duplicate_ratio_from_settings`: ratio 100 → a near-duplicate pair (one word changed) is not linked; with 88 it is.
  - `test_repeat_window_from_settings`: window 1 day → a complaint 3 days earlier is not counted.
  - `test_import_rows_from_settings`: max 10 → an 11-row CSV raises `ImportFileError("At most 10 rows per file.")`.
  - `test_chat_questions_from_settings`: max 2 → the intake must summarise after 2 questions.
  - integration `test_attachment_count_from_settings`: max 1 → second upload 422 "A complaint can have at most 1 attachments."
  - integration `test_attachment_size_from_settings`: max 1 MB → a 1.5 MB file → 422.
  - integration `test_chat_message_length_from_settings`: max 200 → a 300-character message → 422 "Messages are limited to 200 characters."
- [ ] **Step 2: Run** both files — Expected: FAIL.
- [ ] **Step 3: Implement**: read `runtime().intake` at each check; upload routes read `max_attachment_mb * 1024 * 1024 + 1` bytes.
- [ ] **Step 4: Run** `make lint && make test` — Expected: clean, all PASS.
- [ ] **Step 5: Commit** `feat(intake): limits and duplicate thresholds read the settings`.

### Task 4: Analytics, SLA, shop and storefront readers

**Files:**
- Modify: `src/analytics/trends.py`, `src/api/routes/analytics.py`, `complaint_processing/sla.py`, `storefront/queries.py`, `storefront/automation.py`, `src/api/routes/storefront.py`, `support_chat/intake.py` (`faq_entries`), `tests/unit/test_storefront_config.py` (FAQ test uses `filled` over the settings FAQ)
- Test: `tests/unit/test_analytics_shop_settings.py`, `tests/integration/test_storefront_settings.py`

**Interfaces:**
- Consumes: `runtime().analytics`, `runtime().shop`, `runtime().orders.delay_wait_steps`, `storefront.faq.filled`.

- [ ] **Step 1: Write the failing tests:**
  - `test_resolved_statuses_from_settings`: resolved `["resolved"]` → `on_status_change(c, "closed", now)` leaves `resolved_at` None; default sets it.
  - `test_trend_min_count_from_settings` (db): one complaint in a group, `trend_min_count` 1 and `trend_rise_ratio` 1.0 → reported; default → not.
  - `test_dashboard_limit_from_settings` (db): limit 5 → SLA-risk/trend lists ≤ 5.
  - `test_best_seller_window_from_settings` (db): order 30 days old counted with 90, not with 7.
  - `test_delay_wait_from_settings`: a delayed order waits `step * delay_wait_steps` (value 1 vs 3).
  - `test_storefront_config_uses_settings` (db): saved FAQ answer "Ships in {standard_days} days." → `GET /storefront/config` FAQ contains "Ships in 5 days."; socials equal the saved list.
  - `test_chat_faq_uses_settings`: `faq_entries()` answers equal the filled settings FAQ.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement**; `sla_config()` returns the two lists from settings; `get_storefront_config` sets `faq=[FaqItem(question, filled(answer))]` and `company.socials` from settings.
- [ ] **Step 4: Run** `make lint && make test` — Expected: clean, all PASS.
- [ ] **Step 5: Commit** `feat(settings): analytics, SLA statuses and shop read the settings`.

### Task 5: Analytics, Intake and Shop tabs

**Files:**
- Create: `web/src/components/settings/analytics-settings.tsx`, `web/src/components/settings/intake-settings.tsx`, `web/src/components/settings/shop-settings.tsx`
- Modify: `web/src/components/settings/settings-manager.tsx` (tabs after Validation; `delay_wait_steps` on Orders)

**Interfaces:**
- Consumes: Task 2 generated types (`AnalyticsSettings`, `IntakeSettings`, `ShopSettings`), `data.complaint_statuses`, `data.policy_values`, `listCategoriesOptions()`, `Field`/`NumberInput` from `fields.tsx`. Each tab component takes `{ value, defaults, onChange(patch) }` (+ `categories`/`statuses` for Analytics, `policyValues` for Shop).

- [ ] **Step 1: Build** per spec §4. Intake help texts: chat message "200 to 2,000; the chat box never accepts more than 2,000", description max "500 to 5,000; the contact form never accepts more than 5,000". Shop FAQ: question/answer inputs, up/down/remove, Add; placeholder list `{name}` = value; preview line per answer filled client-side (unknown placeholders left as typed). Rows fit narrow widths (no horizontal scroll).
- [ ] **Step 2: Verify** `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` — Expected: 0 errors.
- [ ] **Step 3: Browser check** (admin signed in): description max 100 → Save → shop contact form with 150 characters refused with "at most 100" → Reset → Save; edit FAQ answer 1 → Save → Help page shows it → Reset → Save; no horizontal scroll at the pane width.
- [ ] **Step 4: Commit** `feat(web): Analytics, Intake and Shop settings tabs`.

### Task 6: Documentation and full check

**Files:** `documentation/user_guide.md` (Analytics, Intake, Shop rows; Orders row mentions the delay wait), `documentation/evaluator_guide.md` (row "Change the complaint length limit | Settings → Intake → Save | Database (no code)"), `documentation/project_report.md` (note).

- [ ] **Step 1:** write the changes.
- [ ] **Step 2:** `make lint && make test` (all pass) and `pnpm --dir web build` (clean).
- [ ] **Step 3:** `git commit -m "docs: analytics, intake and shop settings"`
