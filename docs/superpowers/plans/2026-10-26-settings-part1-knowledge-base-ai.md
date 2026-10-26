# Settings Part 1 (Knowledge base & AI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chunk size, overlap, upload limit, search tuning, document types/precedence and the AI timeout, attempts and reasoning switch become admin settings, with a "Reprocess all active documents" button.

**Architecture:** A new `knowledge_base` group and three new `ai` fields in the existing run-time settings (`app_settings`); defaults come from today's environment values, constants and `config/knowledge_base.yaml`. Each reader switches from `get_settings()`/constants/YAML to `app_settings.runtime()`. A new endpoint re-queues every active document version through the existing ingest job.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2, Celery, pytest; Next.js 16, TanStack Query, generated @hey-api client.

**Spec:** `docs/superpowers/specs/2026-10-26-settings-part1-knowledge-base-ai-design.md`

## Global Constraints

- Limits (spec §1): `chunk_max_tokens` 100–480 (default 450); `chunk_overlap_tokens` 0 to `chunk_max_tokens − 50` (default 60); `max_upload_mb` 1–50 (default 20); `retrieval_candidates` 5–100 (default 30); `rrf_k` 1–200 (default 60); `document_types` 1–30 entries, `code` matches `^[a-z][a-z0-9_]{1,39}$` and is unique, `name` 3–60 chars single line, `precedence` 1–9; `ai.timeout_seconds` 10–300 (default 60); `ai.max_attempts` 1–3 (default 2); `ai.openai_reasoning` bool (default true).
- Defaults are read from today's sources (`Settings.chunk_max_tokens`, `chunk_overlap_tokens`, `max_upload_mb`, `genai_timeout_seconds`, `genai_max_attempts`, `openai_reasoning`; `retrieval.CANDIDATES_PER_RANKER`=30, `RRF_K`=60; `config/knowledge_base.yaml`). With nothing stored, behaviour is unchanged.
- Removing a document type in use → 422 with exactly: "`<code>` is used by N documents (`DOC-A`, `DOC-B`); retire or re-type them first." (backticks are not part of the message).
- Reprocess endpoint `POST /api/v1/documents/reprocess-active` → 202 `{"queued": N}`; audit action `knowledge_base.reprocess_all` with `{"queued": N, "chunk_max_tokens": …, "chunk_overlap_tokens": …}`.
- UI copy: tab "Knowledge base"; button "Reprocess all active documents"; note "New uploads use these sizes immediately; existing documents keep their passages until reprocessed."; after click "Reprocessing N documents…".
- Commits: one per task, no `Co-Authored-By` line.

## Review Focus

- An admin saves chunk size and immediately presses Reprocess; the worker's 15-second cache still holds the old size → Task 3 tests ingestion with a value saved after the cache was filled.
- A stored `knowledge_base` value goes bad (e.g. hand-edited row) and wipes the AI provider and e-mail settings too → Task 1 tests per-group fallback.
- The AI provider object is cached by (provider, model, effort); a new timeout or reasoning value is silently ignored until restart → Task 3 tests that changing the timeout changes the built provider.
- An admin lowers the upload limit below the size of a file that is mid-upload in another tab; the route reads `limit + 1` bytes → Task 3 tests the 422 path with the setting at 1 MB.
- Reprocess-all pressed twice quickly re-queues versions already pending → Task 4 tests that a second call re-queues the same N (idempotent marking, no error) and still writes one audit entry per call.

---

### Task 1: Settings model, defaults and per-group fallback

**Files:**
- Modify: `app_settings/model.py`, `app_settings/defaults.py`, `app_settings/store.py`
- Test: `tests/unit/test_kb_ai_settings.py`

**Interfaces:**
- Produces:
  - `app_settings.model.DocumentTypeSetting(BaseModel)`: `code: str`, `name: str`, `precedence: int` (limits from Global Constraints)
  - `app_settings.model.KnowledgeBaseSettings(_Group)`: `chunk_max_tokens: int`, `chunk_overlap_tokens: int`, `max_upload_mb: int`, `retrieval_candidates: int`, `rrf_k: int`, `document_types: list[DocumentTypeSetting]`; a model validator enforces overlap ≤ chunk − 50 and unique codes.
  - `AiSettings` gains `timeout_seconds: float`, `max_attempts: int`, `openai_reasoning: bool`.
  - `RuntimeSettings.knowledge_base: KnowledgeBaseSettings` (required field; `defaults()` supplies it).
  - `app_settings.store.load(data)` validates **each group separately**: a group that fails falls back to that group's defaults (log `settings.invalid_group` with the group name); others keep stored values.
  - `app_settings.store.runtime(fresh: bool = False) -> RuntimeSettings`: `fresh=True` re-reads the row (still honours `override`), and refreshes the cache.

- [ ] **Step 1: Write the failing tests** (`tests/unit/test_kb_ai_settings.py`)

```python
def test_defaults_equal_today():
    d = app_settings.defaults()
    kb = d.knowledge_base
    assert (kb.chunk_max_tokens, kb.chunk_overlap_tokens, kb.max_upload_mb,
            kb.retrieval_candidates, kb.rrf_k) == (450, 60, 20, 30, 60)
    assert [(t.code, t.precedence) for t in kb.document_types][:2] == [("compliance", 1), ("policy", 2)]
    assert len(kb.document_types) == 9
    assert (d.ai.timeout_seconds, d.ai.max_attempts, d.ai.openai_reasoning) == (60.0, 2, True)

@pytest.mark.parametrize("field,value", [("chunk_max_tokens", 99), ("chunk_max_tokens", 481),
    ("max_upload_mb", 0), ("max_upload_mb", 51), ("retrieval_candidates", 4), ("rrf_k", 201)])
def test_kb_limits(field, value): ...  # model_validate with the change raises ValidationError

def test_overlap_must_leave_50_tokens():  # chunk 200, overlap 151 → error; overlap 150 → ok

def test_document_type_rules():  # duplicate code, code "Policy", name "ab", precedence 0/10 → each raises

@pytest.mark.parametrize("field,value", [("timeout_seconds", 9), ("timeout_seconds", 301),
                                         ("max_attempts", 0), ("max_attempts", 4)])
def test_ai_limits(field, value): ...

def test_bad_kb_group_resets_only_that_group():
    s = load({"knowledge_base": {"chunk_max_tokens": 5}, "email": {"mailbox_check_seconds": 120}})
    assert s.knowledge_base.chunk_max_tokens == 450 and s.email.mailbox_check_seconds == 120
```

- [ ] **Step 2: Run** `uv run pytest tests/unit/test_kb_ai_settings.py -q` → FAIL (no `knowledge_base` attribute).

- [ ] **Step 3: Implement** the models, `defaults()` additions (read the env settings, the two retrieval constants and `config/knowledge_base.yaml` via `yaml.safe_load` — not via `get_kb_config()`, which Task 3 rewires to settings), per-group `load()`, and `runtime(fresh=...)`. Keep the existing test `test_invalid_stored_values_fall_back_to_defaults` true for the e-mail group (it now resets only `email`).

- [ ] **Step 4: Run** `uv run pytest tests/unit/test_kb_ai_settings.py tests/integration/test_app_settings_store.py tests/unit/test_app_settings_model.py -q` → PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check . && uv run mypy .
git add app_settings tests/unit/test_kb_ai_settings.py
git commit -m "feat(settings): knowledge base and AI values in run-time settings"
```

---

### Task 2: Settings API: save, defaults, document types in use

**Files:**
- Modify: `src/api/schemas.py` (`SettingsUpdate.knowledge_base: KnowledgeBaseSettings`, `SettingsOut.defaults: RuntimeSettings`), `src/api/routes/settings.py`
- Test: `tests/integration/test_settings_api.py` (extend `body()` helper to include `knowledge_base`; new tests)

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `GET /settings` returns `defaults`; `PUT /settings` accepts `knowledge_base`; 422 when a removed type is in use (message per Global Constraints, documents listed by `doc_code`, sorted).

- [ ] **Step 1: Write failing tests:** `test_admin_saves_knowledge_base_values` (chunk 300 saved and read back; `defaults.knowledge_base.chunk_max_tokens == 450`); `test_removing_a_type_in_use_is_refused` (seed a `Document` with `doc_type="faq"`, `doc_code="FAQ-GEN-01"`; PUT without `faq` → 422 and detail contains "faq is used by 1 documents (FAQ-GEN-01)"); `test_removing_an_unused_type_is_allowed`; `test_access_matrix_kept` (existing test still passes).
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_settings_api.py -q` → new tests FAIL.
- [ ] **Step 3: Implement** the schema fields and, in `update_settings`, the in-use check (query `Document.doc_code` where `doc_type` in removed codes) before saving.
- [ ] **Step 4: Run** the file → PASS; then `make openapi`.
- [ ] **Step 5: Commit**

```bash
git add src tests/integration/test_settings_api.py web/openapi.json web/src/lib/api/generated
git commit -m "feat(settings): save knowledge base settings; protect document types in use"
```

---

### Task 3: Readers use the settings

**Files:**
- Modify: `knowledge_base/ingestion.py`, `knowledge_base/service.py`, `src/api/routes/documents.py`, `knowledge_base/retrieval.py`, `knowledge_base/config.py`, `genai_pipeline/providers.py`, `genai_pipeline/pipeline.py`, `genai_pipeline/evidence.py`
- Test: `tests/integration/test_kb_settings_readers.py`

**Interfaces:**
- Consumes: `app_settings.runtime(fresh=True)` (Task 1).
- Produces:
  - `knowledge_base.config.get_kb_config() -> KnowledgeBaseConfig` built from `runtime().knowledge_base.document_types` (no `lru_cache`; same return type, so its four callers are unchanged).
  - `retrieval.search_chunks(...)` reads `retrieval_candidates` and `rrf_k` once per call and passes them to `_semantic_stmt(vector, candidates)`, `_keyword_stmt(query, candidates)`, `_fuse(rankings, limit, k)`; the module constants are removed.
  - `providers._build_provider(provider, model, effort, timeout_seconds, reasoning)` (cache key includes the two new values); `get_provider()` passes `runtime().ai.timeout_seconds` and `.openai_reasoning`.
  - The analysis retry loop uses `runtime().ai.max_attempts`; ingestion uses `runtime(fresh=True).knowledge_base` for chunk size/overlap; upload checks use `runtime().knowledge_base.max_upload_mb * 1024 * 1024`.

- [ ] **Step 1: Write failing tests** (`tests/integration/test_kb_settings_readers.py`, db-marked):
  - `test_ingestion_uses_chunk_size_saved_after_cache_filled`: call `runtime()` (fills cache), save chunk size 200 / overlap 0 via `app_settings.save`, ingest the long SOP text (6 × the repeated paragraph from the KB test kit) → every chunk `token_count <= 200`, more chunks than with 450, and no chunk starts with the previous chunk's last sentence.
  - `test_upload_limit_from_settings`: override settings with `max_upload_mb=1`; POST a 2 MB `.md` to `/api/v1/documents/upload` as admin → 422, detail contains "the limit is 1 MB".
  - `test_retrieval_reads_candidates_and_k`: monkeypatch `_fuse` to record its `k`; override `rrf_k=10` → recorded 10; defaults → 60.
  - `test_document_types_from_settings`: override with an added type `{code: "notice", name: "Notice", precedence: 3}` → `get_kb_config().type_codes` contains `notice`; a precedence change (faq → 1) is what `python_validation.pipeline` and retrieval read.
  - `test_provider_rebuilt_when_timeout_changes`: override timeout 30 → `get_provider().timeout_seconds == 30`; override 90 → 90 (`OpenAIProvider`/`AnthropicProvider` expose `timeout_seconds`).
  - `test_attempts_from_settings`: override `max_attempts=1` with a scripted provider that returns invalid JSON → exactly 1 call recorded.
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_kb_settings_readers.py -q` → FAIL.
- [ ] **Step 3: Implement** the reader changes listed in Interfaces.
- [ ] **Step 4: Run** the file, then the whole suite `uv run pytest -q` → PASS (defaults keep every existing test green).
- [ ] **Step 5: Commit**

```bash
git add knowledge_base genai_pipeline src/api/routes/documents.py tests/integration/test_kb_settings_readers.py
git commit -m "feat(settings): chunking, uploads, search, document types and AI read the settings"
```

---

### Task 4: Reprocess all active documents

**Files:**
- Modify: `knowledge_base/service.py` (`reprocess_active(db, actor) -> int`), `src/api/routes/documents.py`, `src/api/schemas.py` (`ReprocessAllOut: queued: int`)
- Test: `tests/integration/test_reprocess_all.py`

**Interfaces:**
- Consumes: existing `_safe_enqueue(version_id)`; `require_access("knowledge_base", "edit")`.
- Produces: `POST /api/v1/documents/reprocess-active` → 202 `ReprocessAllOut`.

- [ ] **Step 1: Write failing tests:** with 2 active versions and 1 superseded (use the `client` fixture; `app.state.enqueued` records queued ids): admin → 202 `{"queued": 2}`, `enqueued` holds exactly the 2 active ids, both now `ingest_status == "pending"` and still `status == "active"`; one `AuditEvent` `knowledge_base.reprocess_all` with `after == {"queued": 2, "chunk_max_tokens": 450, "chunk_overlap_tokens": 60}`; calling twice → second also 202 `{"queued": 2}` and two audit events; agent (default: KB view only) → 403; reviewer with KB edit granted via `app_settings.override` → 202.
- [ ] **Step 2: Run** → FAIL (404).
- [ ] **Step 3: Implement** `reprocess_active` (select versions with `status == ACTIVE`, set pending, clear `ingest_error`, one audit event, commit, enqueue each) and the route.
- [ ] **Step 4: Run** the file and `uv run pytest -q` → PASS; `make openapi`.
- [ ] **Step 5: Commit**

```bash
git add knowledge_base/service.py src tests/integration/test_reprocess_all.py web/openapi.json web/src/lib/api/generated
git commit -m "feat(kb): reprocess all active documents"
```

---

### Task 5: Settings page: Knowledge base tab, AI fields, defaults, reprocess button

**Files:**
- Modify: `web/src/components/settings/settings-manager.tsx`
- Create: `web/src/components/settings/document-types-editor.tsx`

**Interfaces:**
- Consumes: generated `SettingsOut.defaults`, `SettingsUpdate.knowledge_base`, `reprocessActiveDocumentsMutation` (name as generated from the route function `reprocess_active_documents`).

- [ ] **Step 1: Implement:**
  - `toForm` includes `knowledge_base`.
  - New tab **Knowledge base**: NumberInput fields with the Global Constraints limits (overlap max = chunk − 50); help text per field (chunk: "Embedding model reads at most 512 tokens"; RRF k: "Standard value 60"); the note and **Reprocess all active documents** button (confirm dialog via `window.confirm`; success toast "Reprocessing N documents…").
  - `DocumentTypesEditor({ value, onChange, inUse })`: rows code/name/precedence, add row, remove row; `inUse: Record<string, string[]>` maps a type code to the `doc_code`s using it, built from `listDocumentsOptions()` (each document's `doc_type` and `doc_code`); remove is disabled for codes in `inUse`, with tooltip "Used by DOC-A, DOC-B".
  - AI tab: Timeout (s) 10–300, Attempts 1–3, OpenAI reasoning switch.
  - Each field shows "Default: X" with a **Reset** link that sets the value from `defaults`.
- [ ] **Step 2: Verify** `pnpm --dir web typecheck && pnpm --dir web lint && pnpm --dir web build` → clean.
- [ ] **Step 3: Browser check** (signed in as admin, local servers): change chunk size to 200 → Save → Reprocess all → after ~1 min a long policy shows more passages; Reset → 450 → Save → Reprocess all. Remove the `faq` type → Save → error message lists FAQ-GEN-01. If no signed-in session is available, record it in the ledger and ask the user.
- [ ] **Step 4: Commit**

```bash
git add web/src
git commit -m "feat(web): Knowledge base settings tab, AI limits and reprocess button"
```

---

### Task 6: Documentation and full check

**Files:** `documentation/user_guide.md` (Settings → Knowledge base section), `documentation/evaluator_guide.md` (section 5 row: "Change chunk size | Settings → Knowledge base → chunk size → Save → Reprocess all active documents | Database (no code)"), `documentation/project_report.md` (§17 note: sizes are settings).

- [ ] **Step 1: Write the doc changes.** The study guide PDF now lives outside the repository (demo kit); note in the final message that its chunking answer should be regenerated.
- [ ] **Step 2:** `make lint && make test` (all pass, more than 564 tests) and `pnpm --dir web build` (clean).
- [ ] **Step 3: Commit** `git commit -m "docs: knowledge base and AI settings"`
