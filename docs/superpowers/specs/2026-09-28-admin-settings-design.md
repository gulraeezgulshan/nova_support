# Admin settings and branding: design

Date: 2026-09-28. Status: approved in conversation (approach A), awaiting spec review.

## Goal

Administrators change operational behaviour and branding from a Settings page in the staff
console, without redeploying: e-mail timing, AI behaviour, review thresholds, SLA scan timing,
shop and console names and logos, and contact details. Secrets stay in environment variables.

## Decisions (from the conversation)

- All four groups are editable: e-mail and timing, AI behaviour, operations and SLA, branding.
- Two brands: the **shop** (VoltHaven) and the **console** (SupportNova), each with a name and
  logo. The shop logo is also the browser-tab icon.
- Policy numbers (warranty, returns, delivery) are **read-only** in Settings and labelled with
  their source policy document; they change by uploading a new policy version, so the shop,
  the AI and the Python rules can never disagree.
- Live timings use **approach A**: one Beat `tick` every 15 seconds and a database gate per job.
- Secrets (API keys, passwords, database and Redis URLs) are never stored in or returned by
  Settings.

## 1. Settings model and storage

`app_settings/model.py` defines `RuntimeSettings` (Pydantic, `extra="forbid"`) with four groups:

| Group | Field | Type / limits | Default (today's value) |
|---|---|---|---|
| `email` | `mailbox_check_seconds` | int 60–3600 | 60 |
| | `outbox_flush_seconds` | int 15–600 | 30 |
| | `from_name` | str 1–80 | `MAIL_FROM_NAME` |
| | `auto_replies` | bool | true |
| `ai` | `provider` | `openai` \| `anthropic` | `GENAI_PROVIDER` |
| | `model` | str 1–100 | `OPENAI_MODEL` / `ANTHROPIC_MODEL` for the provider |
| | `effort` | none…max (existing literal) | `GENAI_EFFORT` |
| | `retrieval_limit` | int 3–20 | `RETRIEVAL_LIMIT` (8) |
| | `auto_analysis` | bool | true |
| `operations` | `sla_scan_minutes` | int 1–60 | `analytics.yaml` (5) |
| | `verified_min_score` | int 50–100 | `validation.yaml` (80) |
| | `always_review_escalation_level` | int 1–5 | `validation.yaml` (4) |
| `branding` | `shop_name`, `shop_tagline` | str 1–60 / 0–140 | `storefront.yaml` company |
| | `console_name` | str 1–40 | "SupportNova" |
| | `support_email`, `phone`, `address`, `hours` | str, e-mail validated | `storefront.yaml` company |
| | `shop_logo_key`, `console_logo_key` | str \| null (storage key, set only by upload) | null |

- Table `app_settings`: one row (`id = 1`), `data JSONB`, `version int`, `updated_at`,
  `updated_by_id`. Migration creates it empty; the first read builds defaults from the
  environment and config files, so behaviour is unchanged until an admin saves.
- Stored data is **partial**: only fields an admin changed are stored; everything else keeps
  following its default. Loading merges defaults with stored data and validates the result.
- `app_settings.runtime()` returns the merged settings, cached in-process for 15 seconds
  (`reset_cache()` for tests and immediately after a save in the same process).
- Save: `PUT /api/v1/settings` (admin) with the full editable document and the `version`
  the admin loaded; a stale `version` returns 409 (two admins cannot overwrite each other
  silently). The save writes an audit event `settings.updated` with before and after.
- `GET /api/v1/settings` (admin) returns the settings, `version`, `updated_at`, the name of
  who changed them, which providers have an API key (`providers_available`), suggested
  models per provider, and the read-only policy facts with their source document code and
  version.

## 2. Validation rules beyond types

- `ai.provider` must have its API key configured, else 422 "Add ANTHROPIC_API_KEY on
  Railway first" (never reveals a key).
- Branding text is sanitised like other free text (control characters removed).
- Logo keys can only be set through the upload endpoint, not through `PUT /settings`.

## 3. Where settings are used

| Setting | Consumer (today) | Change |
|---|---|---|
| mailbox / outbox interval, SLA scan | `src/worker.py` beat schedule | replaced by the tick gate (section 4) |
| `from_name` | `email_channel/tasks.build_message`, `transport.BrevoSender` | read `runtime().email.from_name` |
| `auto_replies` | `email_channel/notify.after_validation`, `support_chat/notify.after_validation` (`AUTO_REPLY_VERDICTS`), `python_validation` review decision | when false, verified/corrected drafts are not sent: the complaint is sent to manual review with the reason "Automatic replies are off: approve the reply", the customer gets the holding message, and the reply goes out when a reviewer approves it (as for needs-review today) |
| provider / model / effort | `genai_pipeline/providers.get_provider` | built from `runtime().ai`; the API key still comes from the environment |
| `retrieval_limit` | `genai_pipeline/pipeline.py` | read `runtime().ai.retrieval_limit` |
| `auto_analysis` | automatic triggers: intake (`complaint_processing/service.py`), chat confirm, inbound e-mail, bulk import | these call `enqueue_if_automatic()`, which queues only when on; manual "Re-run analysis" and reviewer "Regenerate" always queue |
| thresholds | `python_validation/checks.py` via `validation_config()` | the two values are overridden from `runtime().operations` |
| branding | `storefront.config.storefront_config()` company block, web header/footer, console sidebar, favicon | company fields come from `runtime().branding`; policy numbers stay in `storefront.yaml` |

`AnalysisRun` and the evidence pack keep recording the provider, model and effort actually
used, so a settings change is traceable per analysis.

## 4. Scheduler: tick and job gate

- Beat schedules one task, `app_settings.tasks.tick`, every 15 seconds.
- Table `job_runs(job text primary key, last_run_at timestamptz)`.
- `claim(job, interval_seconds, now)` runs one statement:
  `INSERT … ON CONFLICT (job) DO UPDATE SET last_run_at = :now WHERE job_runs.last_run_at <= :now - interval RETURNING job`.
  It returns true for exactly one caller per interval, even with overlapping ticks or two
  workers.
- `tick()` reads `runtime()` and, for each of `mailbox-check`, `email-outbox`,
  `sla-risk-scan`, claims and runs the existing task body (`check()`, `flush()`,
  `scan_sla`). Each job's failure is logged and does not stop the others.
- Existing tasks keep their names, so they can still be run by hand.

## 5. Logos

- `POST /api/v1/settings/logo/{target}` (admin, `target` = `shop` | `console`), multipart
  `file`: PNG, JPEG or WebP, ≤ 1 MB, type checked from the file content (same approach as
  complaint attachments); SVG and anything else is refused with 422. Stored under
  `branding/{target}-{sha256[:12]}.{ext}`; the key is saved in settings (audited).
- `DELETE /api/v1/settings/logo/{target}` (admin) removes it; the text badge returns.
- `GET /api/v1/branding` (**public**): names, tagline, contact details and logo URLs.
- `GET /api/v1/branding/logo/{target}` (**public**): the image with `Cache-Control: public,
  max-age=300`, `X-Content-Type-Options: nosniff`; 404 when none.

## 6. Web

- New page **Settings** (`/settings/general`, admin only) under Administration, tabs:
  E-mail & timing · AI · Operations · Branding · Policy facts. Each tab: labelled fields with
  help text and limits, Save (disabled until changed), "Last changed by … on …", clear error
  messages, 409 shows "Someone else changed the settings; reload".
- Branding tab: logo upload with preview and Remove, for shop and console.
- Shop header and footer, console sidebar and the browser-tab icon use `GET /branding`
  (fetched server-side, revalidated every 60 s); without a logo they show the current badge.
- Policy facts tab: read-only table (fact, value, source document and version).

## 7. Error handling

- Invalid values: 422 with the field and reason; nothing saved.
- Settings table unreadable: `runtime()` logs and returns the defaults, so the system keeps
  working with today's behaviour.
- Tick: one job failing does not stop the others; the gate still advanced, so a failing job
  is retried at its next interval rather than every 15 seconds.

## 8. Tests

- Model: defaults equal today's values; limits reject out-of-range values; unknown fields
  rejected; stored partial data merges with defaults.
- API: admin reads and saves; agent/customer get 403; stale version 409; provider without a
  key 422; audit event written; secrets never appear in the response.
- Consumers: `from_name` in outgoing e-mail; auto-replies off → no reply queued for a
  verified verdict (e-mail and chat), holding message instead and the complaint in the review queue; auto-analysis off → no
  analysis queued at intake, manual re-run still queues; thresholds change the verdict;
  retrieval limit passed to search; provider built from settings.
- Scheduler: `claim` true once per interval and false inside it; tick runs only due jobs
  and continues after a failing job; beat schedules only the tick.
- Logos: PNG accepted and served publicly; SVG, oversized and fake-extension files refused;
  delete returns 404 afterwards; agent cannot upload.
- Web: lint, types and `next build`; the page checked in the browser.

## Out of scope

- Editing policy numbers (done by uploading a new policy version).
- Changing secrets or infrastructure (Railway variables).
- Per-department or per-user settings; settings history beyond the audit trail.
