# Settings, Part 4b: customer texts on their own Settings page

Date: 2026-10-30. Status: design approved in conversation, awaiting spec review.

## Context

The last part of the settings work (Parts 1–4a are done and pushed). It moves the fixed
customer-facing texts — order e-mails (`config/order_emails.yaml`), complaint e-mails and the
e-mail signature (`email_channel/outbound.py`), and the chat assistant's fixed lines
(`support_chat/service.py`, `support_chat/intake.py`) — to a new page with placeholder checks and
a live preview. Agreed in conversation: own page (like Patterns), preview only (no test send).

## Goal

An administrator edits these texts on **Settings → Customer texts**, sees each one filled with
sample values while typing, and saves; the next e-mail or chat uses the new wording (within about
15 seconds), without a redeploy.

## 1. Settings, defaults and checks

New group `texts` in the run-time settings, stored like the others (only changes from the
defaults; per-group fallback to defaults when a stored group is invalid). Defaults are today's
wording, except that the literal "VoltHaven" in the complaint e-mails, the signature and the chat
greeting becomes `{shop}` (same output while the shop name is VoltHaven).

| Part | Texts | Allowed placeholders | Required | Length |
|---|---|---|---|---|
| `order_emails` | exactly `placed, shipped, delayed, delivered, cancelled, returned, return_refused`, each `{subject, body}` | `{name} {order_ref} {product} {amount} {date} {shop}` | — | subject 5–150, body 20–2000 |
| `complaint_emails.acknowledgement` | | `{name} {ref} {shop}` | `{ref}` | 20–2000 |
| `complaint_emails.holding` | | `{name} {ref} {shop}` | `{ref}` | 20–2000 |
| `complaint_emails.rejected` | | `{name} {reason} {shop}` | `{reason}` | 20–2000 |
| `complaint_emails.duplicate` | | `{name} {ref} {shop}` | `{ref}` | 20–2000 |
| `complaint_emails.signature` | added to every complaint e-mail, including AI replies and approved responses | `{shop}` | — | 0–300 |
| `chat.greeting` | | `{shop}` | — | 5–500 |
| `chat.ask_what_happened` | | `{product}` | — | 5–500 |
| `chat.fallback_questions` | exactly 3, in order: what happened, when, what the customer wants (the third answer becomes the requested resolution) | none | — | 5–500 each |
| `chat.neutral_question`, `chat.summary_lead`, `chat.faq_follow_up` | | none | — | 5–500 |
| `chat.added_to_complaint` | | `{ref}` | `{ref}` | 5–500 |
| `chat.submitted` | | `{ref}` | `{ref}` | 5–500 |

Checks (model validation, always): only the allowed placeholders for that text; no broken braces,
positional (`{}`, `{0}`) or attribute/index fields; required placeholders present; exactly 3
fallback questions; lengths. Messages name the text, e.g. "Order e-mail shipped, body: unknown
placeholder {foo}; use one of {name}, {order_ref}, {product}, {amount}, {date}, {shop}." and
"Chat submitted must include {ref}."

## 2. Readers

Each reader reads `app_settings.runtime().texts` when it composes, so a saved text applies within
15 seconds. `{shop}` is always the Branding shop name.

| Texts | Reader |
|---|---|
| order e-mails | `storefront/order_emails.py` `queue_order_email` (the YAML becomes the default source only) |
| complaint e-mails and signature | `email_channel/outbound.py` `compose()`; a new `signature()` used by `email_channel/notify.py` for replies and approved responses |
| greeting, ask-what-happened, added-to-complaint, submitted | `support_chat/service.py` |
| fallback questions, neutral question, summary lead, FAQ follow-up | `support_chat/intake.py` |

Unchanged: complaint thread subjects ("Re: … [ref]"), AI-written replies, error and validation
messages, the e-mail From name (E-mail settings).

## 3. API (administrators only)

- `GET /api/v1/settings/texts` → `{texts, defaults, version, updated_at, updated_by,
  placeholders, samples}`. `placeholders` maps each text path (e.g. `order_emails.shipped.body`,
  `chat.greeting`) to its allowed names and required names; `samples` maps placeholder → sample
  value (`name` Ayesha, `order_ref` ORD-240001, `product` AeroBook 14, `amount` PKR 249,999,
  `date` 12 Nov 2026, `ref` CMP-000123, `reason` "Description is too short to act on.", `shop` the
  current shop name).
- `PUT /api/v1/settings/texts` `{version, texts}` → saves only `texts`; stale version → 409
  "Someone else changed the settings; reload and try again."; audit `settings.updated` with
  group `texts`; 422 names the text and the problem.

## 4. Page

**Settings → Customer texts** (sidebar entry after Patterns; page access key `settings`). Tabs:
**Order e-mails** (a card per kind: subject input, body textarea), **Complaint e-mails** (four
cards and the signature), **Chat** (the lines; the 3 fallback questions grouped and labelled "1
What happened", "2 When", "3 What the customer wants").

Each text: its allowed placeholders as buttons that insert at the cursor; "Default · Reset"; a
live preview filled from `samples` (complaint e-mails with the signature attached); an unknown
placeholder stays as typed in the preview with a red "unknown placeholder {x}" note. Save/Discard
with the version check. Fits narrow widths (no horizontal scroll).

## 5. Tests

- Defaults reproduce today's output character for character with shop name "VoltHaven": every
  order e-mail subject and body, every complaint e-mail with signature, every chat line.
- Refused: unknown placeholder, broken braces (`{`, `}`, `{}`, `{0}`, `{name.x}`), missing
  required placeholder, 2 or 4 fallback questions, each length bound, unknown or missing order
  e-mail kind.
- Effects (next call uses the saved text): edited "shipped" subject on the next queued order
  e-mail; edited acknowledgement for a new e-mail complaint; edited signature on an approved
  response; edited greeting opens the next chat; edited first fallback question asked without an
  AI key; renaming the shop (Branding) changes the signature.
- API: GET shape (placeholders and samples), save, stale → 409, other groups unchanged, 422 text,
  non-administrators → 403 on both endpoints.
- Web: type check, lint, build; browser: edit the shipped subject → preview updates → insert
  `{product}` with its button → type `{foo}` → warning shown and save refused with the 422 →
  Reset → Save; no horizontal scroll at the pane width.

## 6. Documentation

User guide (Customer texts section), evaluator guide row "Change an order e-mail | Settings →
Customer texts → Order e-mails → Save | Database (no code)", project report note.

## Out of scope

Test sends; new e-mail kinds; AI prompts and AI-written replies; subjects of complaint threads;
translations.
