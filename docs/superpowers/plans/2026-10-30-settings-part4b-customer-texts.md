# Settings Part 4b (Customer texts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Order e-mails, complaint e-mails with the signature, and the chat assistant's fixed lines become admin-editable on a new Settings → Customer texts page with placeholder checks and a live preview.

**Architecture:** A `texts` group in the run-time settings (defaults = today's wording, "VoltHaven" → `{shop}`), one placeholder registry in `app_settings/texts.py` that the model, the readers, the API and the page share, and dedicated `GET/PUT /settings/texts` endpoints like Patterns.

**Tech Stack:** FastAPI, Pydantic 2, pytest; Next.js 16, TanStack Query, generated @hey-api client (`make openapi`).

**Spec:** `docs/superpowers/specs/2026-10-30-settings-part4b-customer-texts-design.md`

## Global Constraints

- Text paths, allowed/required placeholders and lengths exactly as spec §1 (order e-mails: kinds `placed, shipped, delayed, delivered, cancelled, returned, return_refused`, subject 5–150, body 20–2000, `{name} {order_ref} {product} {amount} {date} {shop}`; complaint e-mails 20–2000 with `{name} {ref} {shop}` / rejected `{name} {reason} {shop}`, required `{ref}` (acknowledgement, holding, duplicate) or `{reason}` (rejected); signature 0–300 `{shop}`; chat lines 5–500: greeting `{shop}`, ask_what_happened `{product}`, fallback_questions exactly 3 (none), neutral_question / summary_lead / faq_follow_up (none), added_to_complaint and submitted `{ref}` required).
- Error texts: `<Label>: unknown placeholder {x}; use one of {a}, {b}.` / `<Label>: braces must wrap a placeholder name` / `<Label> must include {ref}.` where `<Label>` is e.g. `Order e-mail shipped, body`, `Complaint e-mail acknowledgement`, `Chat submitted`, `Chat fallback question 2`.
- Samples: `name` Ayesha, `order_ref` ORD-240001, `product` AeroBook 14, `amount` PKR 249,999, `date` 12 Nov 2026, `ref` CMP-000123, `reason` Description is too short to act on., `shop` = Branding shop name.
- `{shop}` is always `runtime().branding.shop_name`.
- Commit after each task, no `Co-Authored-By` line. Never commit `documentation/architecture.drawio`.

## Review Focus

1. A text that drops `{ref}` would send a customer an acknowledgement with no reference — refused on save — Task 1 `test_required_placeholders`.
2. A placeholder whose value contains braces (a product named `{X}` or a reason with `{`) must not break `str.format` — values are inserted, never re-parsed — Task 2 `test_values_with_braces_are_inserted_literally`.
3. A stored texts group that fails a later check (e.g. a placeholder removed from the registry) falls back to defaults, never stops e-mails — Task 1 `test_bad_texts_group_resets_only_that_group`.
4. Saving texts leaves every other settings group unchanged — Task 3 `test_save_keeps_other_groups`.
5. The page never hard-codes placeholder names; it uses `placeholders` from the API — Task 4 (type check: the component reads `data.placeholders`).

---

### Task 1: Texts model, registry and defaults

**Files:**
- Create: `app_settings/texts.py`, `tests/fixtures/customer_texts_today.json` (generated once from today's code, before any reader changes)
- Modify: `app_settings/model.py`, `app_settings/defaults.py`
- Test: `tests/unit/test_text_settings.py`

**Interfaces:**
- Produces (`app_settings/texts.py`): `ORDER_EMAIL_KINDS: tuple[str, ...]`; `PLACEHOLDERS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]` (path → (allowed, required)) for every text path (`order_emails.<kind>.subject|body`, `complaint_emails.<name>`, `chat.<line>`, `chat.fallback_questions`); `label(path: str, index: int | None = None) -> str`; `placeholder_problem(text: str, allowed: tuple[str, ...]) -> str | None`; `render(text: str, **values: str) -> str` (fills only known names via `string.Formatter().parse`, inserting values literally); `SAMPLES: dict[str, str]` (without `shop`).
- Produces (`app_settings/model.py`): `OrderEmailText(subject, body)`, `ComplaintEmailTexts(acknowledgement, holding, rejected, duplicate, signature)`, `ChatTexts(greeting, ask_what_happened, fallback_questions, neutral_question, summary_lead, faq_follow_up, added_to_complaint, submitted)`, `TextSettings(order_emails: dict[str, OrderEmailText], complaint_emails, chat)`; `RuntimeSettings.texts`.

- [ ] **Step 1: Snapshot today's output.** A one-off script (not committed) writes `tests/fixtures/customer_texts_today.json`: each order e-mail subject/body formatted with SAMPLES + `shop="VoltHaven Electronics"` from `config/order_emails.yaml`; each complaint e-mail via today's `email_channel.outbound.compose(kind, name="Ayesha", ref="CMP-000123", reason=…)`; the signature constant; chat constants (`GREETING`, `ASK_WHAT_HAPPENED.format(product="AeroBook 14")`, `ACKNOWLEDGEMENT.format(ref=…)`, the submitted f-string text with `CMP-000123`, `FALLBACK_QUESTIONS`, `NEUTRAL_QUESTION`, `SUMMARY_LEAD`, `FAQ_FOLLOW_UP`).
- [ ] **Step 2: Write the failing tests:**
  - `test_defaults_reproduce_today`: rendering every default text with SAMPLES and `shop="VoltHaven"` equals the snapshot, character for character (complaint e-mails = body + `"\n\n"` + signature, as today). (Live, `{shop}` is the Branding name "VoltHaven Electronics", so live wording gains "Electronics" — intended, per spec.)
  - `test_unknown_placeholder_refused`: shipped body with `{foo}` → message contains `Order e-mail shipped, body: unknown placeholder {foo}; use one of {name}, {order_ref}, {product}, {amount}, {date}, {shop}.`
  - `test_broken_braces_refused` (parametrized: `"a { b"`, `"a } b"`, `"a {} b"`, `"a {0} b"`, `"a {name.x} b"`, `"a {name[0]} b"`) on `chat.greeting` padded to ≥ 5 chars.
  - `test_required_placeholders`: acknowledgement without `{ref}` → `Complaint e-mail acknowledgement must include {ref}.`; rejected without `{reason}`; `chat.submitted` without `{ref}` → `Chat submitted must include {ref}.`
  - `test_fallback_questions_exactly_three` (2 and 4 refused).
  - `test_lengths` (subject 4 / 151, body 19 / 2001, signature 301, chat line 4 / 501).
  - `test_order_email_kinds_exact` (missing `placed`, extra `refunded` refused).
  - `test_render_inserts_values_literally`: `render("Hi {name}", name="{x}") == "Hi {x}"`.
  - `test_bad_texts_group_resets_only_that_group`: `load({"texts": {"chat": {"greeting": "x"}}, "email": {"mailbox_check_seconds": 120}})` → texts = defaults, email 120.
- [ ] **Step 3: Run** `uv run pytest tests/unit/test_text_settings.py -q` — Expected: FAIL (imports).
- [ ] **Step 4: Implement.** Defaults: order e-mails from the YAML; complaint e-mails and chat lines as literals in `defaults.py` with every "VoltHaven" → `{shop}` (signature `"Kind regards,\n{shop} Customer Care"`).
- [ ] **Step 5: Run** the new tests and `uv run pytest tests/unit -q` — Expected: PASS.
- [ ] **Step 6: Commit** `feat(settings): customer texts in run-time settings`.

### Task 2: Readers

**Files:**
- Modify: `storefront/order_emails.py`, `email_channel/outbound.py`, `email_channel/notify.py`, `support_chat/service.py`, `support_chat/intake.py`, `tests/unit/test_chat_intake.py` (use the settings texts instead of the removed constants)
- Test: `tests/unit/test_text_readers.py`, `tests/integration/test_text_readers_db.py`

**Interfaces:**
- Consumes: `runtime().texts`, `app_settings.texts.render`.
- Produces: `email_channel.outbound.compose(kind, *, name, ref=None, reason=None) -> str` (unchanged signature, body + signature); `email_channel.outbound.signature() -> str` (`"\n\n" + rendered signature`, or `""` when the signature is empty); constants `TEXTS`, `SIGNATURE`, `GREETING`, `ASK_WHAT_HAPPENED`, `ACKNOWLEDGEMENT`, `FALLBACK_QUESTIONS`, `NEUTRAL_QUESTION`, `SUMMARY_LEAD`, `FAQ_FOLLOW_UP` removed; `support_chat/intake.py` helper `_texts()` returning `runtime().texts.chat`.

- [ ] **Step 1: Write the failing tests** (settings via `tests.fixtures.settings.use_settings`):
  - `test_compose_uses_settings`: edited acknowledgement "Got it, {name}: {ref}." → `compose("acknowledgement", name="Ayesha", ref="CMP-1")` starts with "Got it, Ayesha: CMP-1." and ends with the signature.
  - `test_signature_follows_shop_name`: branding shop_name "Nova Mart" → `signature()` ends with "Nova Mart Customer Care".
  - `test_values_with_braces_are_inserted_literally`: `compose("rejected", name="{A}", reason="bad {x}")` contains "{A}" and "bad {x}".
  - `test_fallback_question_from_settings`: edited first fallback question is the reply when no provider.
  - db `test_order_email_uses_settings`: edited shipped subject "Shipped: {order_ref}" → the queued e-mail for a shipped order has that subject.
  - db `test_greeting_from_settings`: edited greeting is the first assistant message of a new chat without an order.
  - db `test_approved_response_gets_signature`: edited signature "Thanks,\n{shop}" ends the queued approved-response e-mail.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** with `render(...)` everywhere (no `str.format` on stored texts).
- [ ] **Step 4: Run** `make lint && make test` — Expected: clean, all PASS.
- [ ] **Step 5: Commit** `feat(texts): e-mails and chat read the customer texts`.

### Task 3: Texts API

**Files:**
- Create: `src/api/routes/texts.py`
- Modify: `src/api/schemas.py` (`TextsOut`, `TextsUpdate`, `PlaceholderRule{allowed, required}`), `src/main.py`, `src/api/routes/settings.py` (general PUT keeps `stored.texts`), `web/openapi.json` + generated client (`make openapi`)
- Test: `tests/integration/test_texts_api.py`

**Interfaces:**
- Produces: `TextsOut{texts, defaults, version, updated_at, updated_by, placeholders: dict[str, PlaceholderRule], samples: dict[str, str]}` (samples include `shop`); operation ids `readTexts`, `updateTexts`; general `GET /settings` leaves `texts` out (like `patterns`).

- [ ] **Step 1: Write the failing tests:** `test_admin_reads_texts` (placeholders["order_emails.shipped.body"].allowed contains "order_ref"; samples["shop"] equals the branding shop name; texts == defaults); `test_save_and_apply` (edited greeting saved, version 1, `runtime(fresh=True).texts.chat.greeting` matches); `test_save_keeps_other_groups`; `test_stale_version_conflict` → 409; `test_unknown_placeholder_422` (detail contains "unknown placeholder {foo}"); `test_staff_forbidden` (agent → 403 on GET and PUT); `test_general_settings_leave_out_texts`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** like `src/api/routes/patterns.py` (save with `audit_group="texts"`); `SettingsGroups` excludes `texts`; `make openapi`.
- [ ] **Step 4: Run** `make lint && make test` and `pnpm --dir web typecheck` — Expected: clean, PASS.
- [ ] **Step 5: Commit** `feat(api): customer texts endpoints`.

### Task 4: Customer texts page

**Files:**
- Create: `web/src/app/(app)/settings/texts/page.tsx`, `web/src/components/settings/texts-manager.tsx`, `web/src/components/settings/text-field.tsx`
- Modify: `web/src/components/app-sidebar.tsx` (entry "Customer texts", `href: "/settings/texts"`, `page: "settings"`, after "Patterns")

**Interfaces:**
- Consumes: `readTextsOptions`, `updateTextsMutation`, `TextsOut`.
- Produces: `TextField({label, value, defaultValue, rule, samples, multiline, suffix?, onChange})` — input/textarea, placeholder buttons that insert `{name}` at the cursor, "Default · Reset", preview (known placeholders filled from samples; unknown ones left as typed plus a red "unknown placeholder {x}" note; `suffix` appends the rendered signature for complaint e-mails).

- [ ] **Step 1: Build** per spec §4: header "Customer texts", description "E-mails and chat messages customers receive. Placeholders in braces are filled in when a message is sent; the preview uses sample values."; tabs Order e-mails / Complaint e-mails / Chat; fallback questions labelled "1 What happened", "2 When", "3 What the customer wants"; Save/Discard with version (409 toast); no horizontal scroll at narrow widths.
- [ ] **Step 2: Verify** `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` — Expected: 0 errors.
- [ ] **Step 3: Browser check** (admin signed in): edit the shipped subject → preview updates; insert `{product}` with its button; type `{foo}` → red note → Save → 422 toast with the message; Reset → Save; no horizontal scroll.
- [ ] **Step 4: Commit** `feat(web): Customer texts settings page`.

### Task 5: Documentation and full check

**Files:** `documentation/user_guide.md` (Customer texts section after Patterns), `documentation/evaluator_guide.md` (row "Change an order e-mail | Settings → Customer texts → Order e-mails → Save | Database (no code)"), `documentation/project_report.md` (note).

- [ ] **Step 1:** write the changes.
- [ ] **Step 2:** `make lint && make test` (all pass) and `pnpm --dir web build` (clean).
- [ ] **Step 3:** `git commit -m "docs: customer texts settings"`
