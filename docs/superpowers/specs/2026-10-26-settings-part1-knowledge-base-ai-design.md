# Settings, Part 1: knowledge base and AI values on the Settings page

Date: 2026-10-26. Status: design approved in conversation, awaiting spec review.

## Context

The user wants every configuration value on the admin Settings page. Agreed in conversation:
four parts, built one after another — **1. knowledge base & AI** (this spec), 2. validation &
classifier, 3. detector word lists, 4. analytics, shop & texts. Out of all parts on purpose:
vocabularies (priorities, urgencies, escalation levels, sentiments), the embedding model and its
384 dimensions, secrets and infrastructure.

## Goal

An administrator changes chunk size, overlap, the upload limit, search tuning, document types
and their precedence, and the AI timeout, attempts and reasoning switch from the Settings page,
without a redeploy; existing documents can be re-chunked with one button.

## 1. Settings, defaults and limits

Stored in the existing run-time settings (`app_settings`): only changes from the defaults are
stored, values are validated, cached 15 s, saved with the shared version (stale save → 409) and
audited (`settings.updated`).

New group `knowledge_base` (Settings tab **Knowledge base**):

| Field | Default (today's source) | Limits |
|---|---|---|
| `chunk_max_tokens` | 450 (`Settings.chunk_max_tokens`) | 100–480 (embedding model reads ≤ 512 tokens) |
| `chunk_overlap_tokens` | 60 (`Settings.chunk_overlap_tokens`) | 0 to `chunk_max_tokens − 50` |
| `max_upload_mb` | 20 (`Settings.max_upload_mb`) | 1–50 |
| `retrieval_candidates` | 30 (`retrieval.CANDIDATES_PER_RANKER`) | 5–100 |
| `rrf_k` | 60 (`retrieval.RRF_K`) | 1–200 |
| `document_types` | the 9 types in `config/knowledge_base.yaml` | 1–30 entries; `code` lowercase `[a-z][a-z0-9_]{1,39}`, unique; `name` 3–60 chars, one line; `precedence` 1–9 |

New fields in the existing `ai` group (tab **AI**):

| Field | Default | Limits |
|---|---|---|
| `timeout_seconds` | 60 (`Settings.genai_timeout_seconds`) | 10–300 |
| `max_attempts` | 2 (`Settings.genai_max_attempts`) | 1–3 |
| `openai_reasoning` | true (`Settings.openai_reasoning`) | bool |

`retrieval_limit` (results given to the AI) already exists in the `ai` group and is unchanged.

**Tolerant loading:** today an invalid stored value makes `load()` return all defaults. Change it
so each group is validated on its own: an invalid group falls back to that group's defaults; the
other groups keep their stored values (logged as `settings.invalid_group`).

## 2. Readers

| Value | Reader (file) | Change |
|---|---|---|
| chunk size / overlap | `knowledge_base/ingestion.py` | read from settings **fresh** (bypassing the 15 s cache) at the start of each ingest, so a reprocess right after saving uses the new values |
| upload limit | `knowledge_base/service.py`, `src/api/routes/documents.py` | `runtime().knowledge_base.max_upload_mb`; the error message states the current limit |
| candidates, RRF k | `knowledge_base/retrieval.py` | read on each search (constants removed) |
| document types | `knowledge_base/config.py` (`get_kb_config()` users: upload checks, `/documents/types`, retrieval precedence, `python_validation/pipeline.py`) | the type list and precedence come from settings |
| timeout, reasoning | `genai_pipeline/providers.py` | from `runtime().ai` |
| attempts | `genai_pipeline/pipeline.py`, `genai_pipeline/evidence.py` | from `runtime().ai` |

Environment variables for these values keep working as the **defaults** (no deployment change).

## 3. Saving rules

- `PUT /api/v1/settings` accepts the new group and fields; it keeps the stored `access` group
  and logo keys as today.
- Removing a document type that any document uses → 422: "`<code>` is used by N documents
  (`DOC-A`, `DOC-B`); retire or re-type them first."
- Overlap must be ≤ chunk size − 50 (validated together).

## 4. Reprocess all active documents

- `POST /api/v1/documents/reprocess-active` (administrator, or a role with Knowledge base
  **edit**) → 202 `{queued: N}`. Marks every **active** version `ingest_status = pending`
  (status stays active), queues the existing `ingest_document_version` job for each, writes one
  audit event `knowledge_base.reprocess_all` with the count and the chunk size/overlap at that
  moment.
- Old passages stay searchable until each document's new passages are written (ingestion
  already deletes and inserts in one transaction).
- Settings page, Knowledge base tab: button **Reprocess all active documents** under the chunk
  fields, with a confirm dialog and the note "New uploads use these sizes immediately; existing
  documents keep their passages until reprocessed." After clicking: "Reprocessing N documents…".
  The Knowledge base page shows each version's progress.

## 5. Settings page

- Tab **Knowledge base**: number fields with their limits; the document types as an editable
  table (code, name, precedence; add row; remove row disabled for types in use, with a tooltip
  naming the documents).
- Tab **AI**: three more fields (timeout, attempts, reasoning switch).
- Every field shows its default and a "Reset to default" link; Save/Discard as today.

## 6. Tests

- Defaults equal today's values; nothing stored → behaviour unchanged.
- Limits refused (each field), overlap rule, document type format and uniqueness.
- Tolerant loading: a bad `knowledge_base` value resets only that group.
- Chunking: chunk size 200 → the long section splits into more passages, each ≤ 200; overlap 0 →
  no repeated sentence; ingestion uses a value saved within the 15 s cache window.
- Upload limit 1 MB → a 2 MB file refused with "the limit is 1 MB".
- Retrieval reads candidates and RRF k; defaults reproduce today's results.
- Document types: precedence change used by retrieval ordering and Python's policy check; new
  type accepted on upload; removing a type in use → 422 with the document list.
- AI: timeout/attempts/reasoning from settings reach the provider and retry loop.
- Reprocess all: only active versions queued; audit written; roles (admin / KB edit allowed,
  others 403); 202 with the count.
- Web: type check, lint, build; browser: chunk size 200 → Save → Reprocess all → more passages on
  a long document; restore 450.

## 7. Documentation

User guide (Settings → Knowledge base), study guide chunking answer (values now changeable),
evaluator guide live-modification row.

## Out of scope

Embedding model and dimensions; the token estimate (words × 1.3); vocabularies; secrets and
infrastructure; Parts 2–4.
