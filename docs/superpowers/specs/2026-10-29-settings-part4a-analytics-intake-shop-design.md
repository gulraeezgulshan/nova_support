# Settings, Part 4a: analytics, intake limits and shop on the Settings page

Date: 2026-10-29. Status: design approved in conversation, awaiting spec review.

## Context

Part 4 of four, split in conversation: **4a** (this spec) moves the remaining numbers and short
lists — analytics and SLA status lists (`config/analytics.yaml`), the intake, duplicate, chat and
import limits (constants in Python code), and the shop's socials, FAQ and two order/shop
numbers — to the Settings page. **4b** (later, own spec) covers the customer texts (order
e-mails, complaint e-mails, chat lines). Out of scope as agreed: vocabularies, the embedding
model, secrets/infrastructure, the AI prompts (versioned with results), the policy numbers
(read-only, from the knowledge-base documents) and the SLA targets (Taxonomy & SLAs).

## Goal

An administrator changes these values on new **Analytics**, **Intake** and **Shop** tabs (and
the existing **Orders** tab) without a redeploy; they apply within about 15 seconds.

## 1. Settings, defaults and limits

Three new groups in the run-time settings (`app_settings`), stored like the others (only
changes from the defaults; per-group fallback to defaults when a stored group is invalid), plus
one field in the existing `orders` group. Defaults are today's values.

### `analytics`

| Field | Default | Limits |
|---|---|---|
| `trend_window_days` | 7 | 1–90 |
| `trend_min_count` | 3 | 1–100 |
| `trend_rise_ratio` | 1.5 | 1.0–10.0 |
| `recurring_min_count` | 3 | 1–100 |
| `watched_categories` | DELIVERY, BILLING | 0–20 unique codes; must exist in the taxonomy (checked on save, active or not) |
| `dashboard_list_limit` | 10 | 5–50 |
| `first_response_statuses` | assigned, in_progress, awaiting_customer, escalated, resolved | 1–9 unique values of `ComplaintStatus` |
| `resolved_statuses` | resolved, closed | 1–9 unique values of `ComplaintStatus` |

`sla.scan_interval_minutes` stays in `operations` (Part 1).

### `intake`

| Field | Default | Limits |
|---|---|---|
| `near_duplicate_min_ratio` | 88 | 70–100 (rapidfuzz token-set ratio, %) |
| `related_min_similarity` | 0.80 | 0.50–0.99 (embedding cosine) |
| `duplicate_window_days` | 30 | 1–365 |
| `repeat_window_days` | 60 | 1–365 |
| `repeat_min_gap_hours` | 24 | 0–168 |
| `min_title_chars` | 5 | 3–20 |
| `min_description_chars` | 20 | 10–200 |
| `min_description_words` | 5 | 1–30 |
| `max_description_chars` | 5000 | 500–5000; must be above `min_description_chars` |
| `max_attachments` | 5 | 0–10 |
| `max_attachment_mb` | 5 | 1–10 |
| `chat_max_questions` | 6 | 2–12 |
| `chat_max_message_chars` | 2000 | 200–2000 |
| `chat_max_customer_messages` | 30 | 5–100 |
| `import_max_rows` | 1000 | 10–5000 |

Upper limits never exceed the fixed caps elsewhere (API schemas: chat message 2 000, contact
message 5 000; bulk file size 5 MB). Settings can lower a limit, not raise it past those caps;
the web forms keep their current `maxLength` and the server reports the stricter setting.

### `shop`

| Field | Default | Limits |
|---|---|---|
| `best_seller_days` | 90 | 7–365 |
| `socials` | Instagram, X, YouTube (from `storefront.yaml`) | 0–8 items `{name 1–30, url}`; url starts with `https://`, ≤ 200 chars |
| `faq` | the 7 items in `storefront.yaml` (unformatted, with placeholders) | 1–20 items `{question 5–200, answer 10–1000}`; placeholders in answers only from the policy values |

Policy placeholders = the keys of `storefront.yaml` `shipping`, `returns` and `warranty`
(e.g. `{standard_days}`, `{window_days}`, `{months}`). An unknown placeholder or broken braces
→ refused: "FAQ 3: unknown placeholder {foo}; use one of {…}."

### `orders` (existing group)

| Field | Default | Limits |
|---|---|---|
| `delay_wait_steps` | 3 | 1–20 |

## 2. Saving

- `PUT /api/v1/settings` accepts optional `analytics`, `intake` and `shop` groups (left out =
  keep stored values), like `knowledge_base` and `validation`; `delay_wait_steps` comes with
  the `orders` group (required group today; older clients without the field keep the default).
- On save, watched categories are checked against the taxonomy: 422 "Watched categories:
  category FOO does not exist."
- `GET /api/v1/settings` returns the new groups in `settings` and `defaults`, plus
  `complaint_statuses` (the `ComplaintStatus` values) and `policy_values` (placeholder name →
  value) for the page.

## 3. Readers

Each reader reads `app_settings.runtime()` when it checks, so a saved value applies within 15
seconds without a restart. The module constants are removed (or kept only as the source of
the default).

| Value | Reader |
|---|---|
| trends, recurring, watched, list limit | `src/analytics/trends.py`, `src/api/routes/analytics.py` |
| first-response / resolved statuses | `complaint_processing/sla.py` `sla_config()` |
| near-duplicate ratio, related similarity | `complaint_processing/duplicates.py` |
| duplicate window, title/description limits | `complaint_processing/service.py` (messages quote the current value) |
| repeat window and gap | `complaint_processing/facts.py` |
| title minimum (fallback titles) | `support_chat/intake.py`, `support_contact/service.py`, `email_channel/inbound.py` |
| attachments count and size | `complaint_processing/attachments.py`, `src/api/routes/attachments.py`, `src/api/routes/mailbox.py` (read size limit + 1 byte) |
| chat questions, message length, message count | `support_chat/intake.py`, `support_chat/service.py` |
| import rows | `bulk_import/reader.py` |
| best-seller window | `storefront/queries.py` |
| delayed-order wait | `storefront/automation.py` |
| socials, FAQ | `GET /storefront/config` (FAQ formatted with the policy values), `support_chat/intake.py` FAQ answers |

## 4. Settings page

New tabs **Analytics**, **Intake**, **Shop** (after Validation); `delay_wait_steps` on the
existing **Orders** tab. Every field: "Default: X · Reset". Save/Discard and version check as
today.

- Analytics: number fields; watched categories as checkboxes from the taxonomy; the two status
  lists as checkboxes of `complaint_statuses`.
- Intake: sections Duplicates, Repeat complaints, Complaint length, Attachments, Chat, Bulk
  import; help texts name the fixed caps (e.g. "200 to 2,000; the chat box never accepts more
  than 2,000").
- Shop: best-seller window; socials table (name, URL; add/remove); FAQ list (question, answer;
  add, remove, move up/down); the placeholder list with values (e.g. `{standard_days}` = 5) and
  a live preview of each answer filled in.

## 5. Tests

- Defaults equal today's constants and YAML.
- Limits refused: each range; `max_description_chars` ≤ `min_description_chars`; empty status
  list; unknown status; duplicate watched category; FAQ unknown placeholder and broken braces;
  social URL without `https://`; list sizes.
- Save: unknown watched category → 422; groups left out keep stored values; GET returns
  `defaults`, `complaint_statuses`, `policy_values`.
- Effects (a saved value applies on the next call):
  - `max_description_chars` 100 refuses a 150-character complaint with "at most 100";
  - `near_duplicate_min_ratio` 100 stops a near-duplicate link;
  - `max_attachments` 1 refuses the second attachment;
  - `chat_max_message_chars` 200 refuses a 300-character chat message;
  - `import_max_rows` 10 refuses an 11-row file;
  - `trend_min_count` 1 reports a group with one complaint;
  - `dashboard_list_limit` 5 returns at most 5 rows;
  - `resolved_statuses` without `closed` keeps a closed complaint's resolution clock open;
  - `best_seller_days` 7 leaves out an order from 30 days ago;
  - a changed FAQ answer and the socials appear in `GET /storefront/config`, placeholders
    filled.
- Web: type check, lint, build; browser: description max 100 → submit a longer complaint on
  the shop (refused with the new message) → Reset → Save; edit an FAQ answer → Help page shows
  it → Reset → Save.

## 6. Documentation

User guide Settings table (Analytics, Intake, Shop rows; Orders row mentions the delay wait),
evaluator guide row "Change the complaint length limit | Settings → Intake → Save | Database
(no code)", project report note.

## Out of scope

Customer texts (Part 4b); policy numbers; SLA targets; vocabularies; prompts; embedding model;
secrets and infrastructure.
