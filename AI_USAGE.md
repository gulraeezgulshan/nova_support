# AI Tool Usage Declaration

Required by SRS section 1.8 (item 19) and deliverable 18. One entry per AI-assisted work
session. Every AI-generated change must be reviewed, tested and understood by the team member(s)
named under **Verified by** before it is merged.

The GenAI API used *inside* the application (Claude API, from Day 2) is part of the
architecture and is documented in the project report, not here.

---

## Entry 1: Day 1 platform foundation

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Architecture planning from the SRS; scaffolding of the Day 1 foundation |
| **Type of assistance** | Technology selection and architecture plan; code generation for backend, frontend, tests, configuration and sample policy documents; running tests, lint and type checks; debugging failures found by those checks |

### Files affected

- Backend: `src/**`, `database/**`, `security/**`, `document_processing/**`, `knowledge_base/**`
- Configuration: `config/*.yaml`, `pyproject.toml`, `alembic.ini`, `docker-compose.yml`, `Dockerfile`, `.env.example`, `Makefile`, `.github/workflows/ci.yml`
- Data: `sample_documents/sources/*.md`, `sample_documents/build_documents.py`
- Frontend: `web/src/**` (app shell, knowledge-base and settings screens), `web/openapi-ts.config.ts`
- Tests: `tests/**`
- Docs: `README.md`, `AI_USAGE.md`

### Changes made

- FastAPI application with Clerk token verification, database-backed roles (customer, agent, reviewer, manager, admin) and an append-only audit trail.
- Configurable taxonomy (categories, subcategories, departments, SLA targets) with admin CRUD endpoints.
- Knowledge-base pipeline: content-based file validation, header-metadata extraction, PDF/DOCX/TXT/MD parsing with section numbers and pages, section-aware chunking, embeddings, policy version lifecycle, hybrid retrieval over active versions, Celery ingestion and a bulk importer.
- Next.js 16 frontend with a role-aware sidebar, knowledge-base management, taxonomy/SLA settings and user-role management, using a client generated from the OpenAPI schema.
- Seven fictional VoltHaven policy documents, including one intentional policy conflict.

### Issues found and fixed during the session

- svix 2.x `Webhook.verify()` no longer returns the payload (found by mypy); the webhook now parses the body after verifying it, with a regression test.
- PDF text contained ligatures ("ﬀ") and merged metadata lines, which broke header extraction on real documents; fixed with NFKC normalisation and label-line handling, with regression tests.
- Keyword retrieval never matched natural-language complaints (AND semantics); changed to OR semantics ranked by coverage.
- Duplicate taxonomy codes returned 500 instead of 409; fixed and tested.

### Tests performed

- 71 automated backend tests (unit + integration against PostgreSQL/pgvector): file validation, metadata, parsing, chunking, version transitions, token verification, RBAC, provisioning, webhook signatures, taxonomy CRUD, upload → ingest → activate → search, supersession, duplicate and invalid uploads.
- Ruff, mypy `--strict`, ESLint, `tsc` and `next build` all pass.
- Manual: real import of the 7 sample documents with the fastembed model; retrieval spot-checks; live API health/readiness, 401 on missing or forged tokens, CORS allow-list; Celery worker processing a queued ingestion job.
- Not yet verified: the signed-in UI in a browser (needs the team's Clerk keys).

### Verified by

| Team member | Modules reviewed | Date |
|---|---|---|
| _to be completed by the team_ | | |

---

## Entry 2: Day 2 complaint intake, rule matrix and GenAI pipeline

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Build complaint intake, the Complaint Resolution Rule Matrix, Pipeline 1, the policy documents and the labelled dataset |
| **Type of assistance** | Design and code generation; writing fictional policy documents, rule rows and dataset scenarios; running tests, lint, type checks and a label-vs-rules audit; fixing the defects those checks found |

### Files affected

- Backend: `complaint_processing/**`, `complaint_rules/**`, `escalation_rules/**`, `routing_rules/**`, `genai_pipeline/**`, `schemas/complaint_analysis.py`, `prompt_templates/complaint_analysis.yaml`, `database/models/{complaints,analysis,rules}.py`, `database/seed.py`, migration `*_complaints_analysis_and_rules.py`, `src/api/routes/{complaints,rules}.py`, `src/api/schemas.py`, `src/core/{config,domain}.py`, `knowledge_base/{retrieval,versioning}.py`
- Configuration: `config/{analysis,actions,detectors}.yaml`, `config/taxonomy.yaml` (quoting fix)
- Data: 13 new policy sources + 1 archived version in `sample_documents/sources/`, `sample_complaints/*`
- Frontend: `web/src/components/complaints/**`, `web/src/components/settings/rules-table.tsx`, complaint and rule-matrix pages, sidebar and dashboard
- Tests: `tests/unit/test_{rule_engine,complaint_intake,genai_contract,dataset}.py`, `tests/integration/test_{complaints_api,analysis_pipeline,rules_api}.py`, `tests/fixtures/genai.py`

### Changes made

- Complaint intake with validation, sanitisation, entity extraction, duplicate rejection and deterministic risk signals.
- A 111-rule matrix (79 resolution, 32 escalation) with a whitelisted condition language, a rule engine and runtime administration API.
- Pipeline 1: taxonomy-driven JSON schema, versioned prompt registry, Claude provider with structured outputs, Python output validation, a single repair retry and manual-review fallback, and full call logging.
- 20 knowledge-base documents (plus an archived version) and a 536-complaint labelled dataset generator and loader.

### Issues found and fixed during the session

- YAML flow syntax silently truncated 24 config values at commas (e.g. action descriptions and department descriptions), and broke the detector regex lists; rewritten in block style, with a regression test that fails on any truncated value.
- Async SQLAlchemy could not lazy-load relationships on new complaints; relationships are now set explicitly.
- `analysis_runs.schema_version` was too short for the full identifier (found by the pipeline tests).
- The amount parser read reference numbers such as `ORD-500037,` as money; fixed with proper thousands-separator handling and a test.
- The label audit found detector false positives ("your policy allows"), weekend off-by-one errors in the generator, near-duplicate resends counted as repeat complaints (now require a 24-hour gap), escalation rules that raised priority for injection attempts, and three escalation thresholds with no supporting policy text (policy text added).
- An older document version imported after a newer one could have displaced it; older versions are now recorded as superseded.

### Tests performed

- 170 automated backend tests pass, including every SRS trap (calm safety complaint, angry low-risk complaint, VIP minor issue, low-value privacy breach, legal threat, repeat complaint, multi-issue routing, prompt injection), pipeline retries, refusals and outages with a scripted provider, and a check that all 531 accepted dataset labels agree with the rule matrix.
- Ruff, mypy `--strict`, ESLint, `tsc` and `next build` pass.
- Manual: imported the 21 documents, loaded the dataset through the real intake path (5 exact duplicates rejected as intended), recomputed signals.
- Not yet verified: live Claude calls and the 20-second latency target (no API key configured yet), and the signed-in UI (no Clerk keys yet).

### Verified by

| Team member | Modules reviewed | Date |
|---|---|---|
| _to be completed by the team_ | | |

## Entry 3: Day 3 ground-truth validation, comparison and manual review

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Build the Python Ground-Truth Validation Pipeline, hallucination checks, the GenAI-vs-Python comparison, manual review, status lifecycle, duplicate linking and policy-update impact analysis |
| **Type of assistance** | Design and code generation; running tests, lint, type checks and the Python-only baseline; fixing the defects those checks found |

### Files affected

- Backend: `python_validation/**`, `hallucination_checks/**`, `comparison_engine/**`, `complaint_processing/{duplicates,review,tasks,service}.py`, `knowledge_base/{impact,ingestion,service}.py`, `database/models/{validation,complaints}.py`, migration `*_validation_review_and_duplicates.py`, `src/api/routes/{review,complaints}.py`, `src/api/schemas.py`, `src/worker.py`, `genai_pipeline/analyze.py`
- Configuration: `config/{classification,validation}.yaml`
- Frontend: `web/src/components/complaints/{validation-panel,review-panel,status-control,review-queue,complaint-view}.tsx`, `web/src/app/(app)/review/page.tsx`, complaint detail page, sidebar, complaints table, regenerated API client
- Tests: `tests/unit/test_validation_checks.py`, `tests/integration/test_validation_and_review.py`, `tests/integration/conftest.py`
- Docs: `README.md`, `Makefile`

### Changes made

- An independent keyword-and-signal classifier that reports its confidence instead of guessing.
- 18 validation checks with severity, evidence and a weighted score; verdicts Verified, Verified with corrections and Needs review. Python enforces safe corrections itself and keeps the more severe value of GenAI and rules.
- Detection of unsupported promises and untraceable facts in drafted customer responses.
- Comparison and Python-only baseline reports (`reports/*.csv`).
- Review queue, eight reviewer actions with before/after records, allowed status transitions, near-duplicate and reworded-repeat linking, and flagging of complaints affected by a policy update.
- Background task that runs analysis then validation, with a Python-only validation when the GenAI provider is down.

### Issues found and fixed during the session

- The priority comparison used a reversed scale, so P3 counted as more severe than P0 (found by unit tests).
- The hallucination check flagged correct response times (SLA and follow-up hours) as untraceable facts.
- The new non-null JSONB column failed on existing rows; the migration now sets a default.
- The status endpoint failed after commit when reading a server-generated timestamp; the complaint is refreshed first.
- A frontend type error on optional check evidence.
- Configuration issue during local setup: the Clerk issuer was still the placeholder, and real Clerk keys had been typed into the committed `web/.env.example`; the template was restored before any commit.

### Tests performed

- 199 automated backend tests pass, including a grounded analysis verified end to end, a missed escalation corrected by Python, a safety complaint escalated with no GenAI output at all, review-queue permissions, every reviewer action and invalid-action error, reclassification re-applying the rules, forbidden status transitions, policy-update impact and near-duplicate linking.
- Python-only baseline on 531 dataset complaints: category 94.9%, department 95.3%, urgency 97.0%, priority 97.0%, escalation 100%.
- Ruff, mypy `--strict`, ESLint, `tsc` and `next build` pass. Signed-in UI loads with Clerk configured.
- Not yet verified: live Claude runs, the GenAI-vs-Python comparison on real model output and the 20-second latency target (no API key configured yet).

### Verified by

| Team member | Modules reviewed | Date |
|---|---|---|
| _to be completed by the team_ | | |
