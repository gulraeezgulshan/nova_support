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

## Entry 4: Day 4 SLA tracking, dashboards, analytics, trends and reports

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Build SLA tracking and risk detection, role-based dashboards, analytics, trend detection, the report suite with CSV/Excel/PDF export, extra search filters and the rule-editing screen |
| **Type of assistance** | Design and code generation; running tests, lint, type checks and the production build; fixing the defects those checks found |

### Files affected

- Backend: `complaint_processing/{sla,tasks,review}.py`, `python_validation/{pipeline,triage}.py`, `src/analytics/**`, `src/api/routes/{analytics,complaints,taxonomy}.py`, `src/api/schemas.py`, `src/main.py`, `src/worker.py`, `src/core/domain.py`, `database/models/complaints.py`, migration `*_sla_tracking.py`, `comparison_engine/report.py`
- Configuration: `config/analytics.yaml`, `docker-compose.yml` (Beat service), `Makefile`, `pyproject.toml` (openpyxl, reportlab)
- Frontend: `web/src/components/{analytics,dashboard}/**`, `web/src/components/settings/{rule-editor,rules-table}.tsx`, `web/src/components/complaints/{complaints-table,complaint-view,badges}.tsx`, dashboard, analytics and reports pages, sidebar, chart component and colours
- Tests: `tests/unit/test_{sla,report_export}.py`, `tests/integration/test_analytics.py`
- Docs: `README.md`

### Changes made

- SLA deadlines, first-response and resolution clocks, six SLA states, and a Celery Beat scan that flags at-risk and breached complaints with timeline and audit entries.
- Customer, agent and management dashboards; an analytics page; trend detection; nine reports exportable as CSV, Excel and PDF.
- Complaint search by sentiment, escalation, SLA status and date range; latest update and resolution status for customers.
- A rule editor for administrators and a vocabulary endpoint so the UI never hard-codes sentiments, priorities, channels or action codes.

### Issues found and fixed during the session

- A result column named `count` clashed with the row's built-in `count()` method, so distribution counts were wrong (found by mypy).
- SQLAlchemy 2.1 deprecates `select().distinct(column)` and `Result.tuples()`; all uses (including earlier code) moved to `distinct_on`, and the suite now runs with those deprecations as errors.
- CORS did not allow `PUT`, which the rule editor needs, and did not expose `Content-Disposition` for export file names.

### Tests performed

- 228 automated backend tests pass, including SLA state transitions, the scan alerting only once, validation starting the SLA clock, KPIs and distributions with filters, trend detection, dashboard permissions, the agent queue order and warnings, every report preview, CSV/Excel/PDF exports, the new complaint filters and the customer's latest update.
- Ruff, mypy `--strict`, ESLint, `tsc` and `next build` pass. All nine reports were generated from the development database in all three formats and the PDF layout was checked visually.
- Not yet verified: the new screens signed in (to be checked by the team in the browser), and dashboards on live GenAI output (no API key configured yet).

### Verified by

| Team member | Modules reviewed | Date |
|---|---|---|
| _to be completed by the team_ | | |

## Entry 5: Day 5 security hardening, evaluation, deployment and documentation

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Security and adversarial tests, sensitive-data redaction, malicious-document quarantine, the unseen hold-out set and evaluation tooling, deployment configuration, GenAI evidence export and the project documentation |
| **Type of assistance** | Design and code generation; writing the hold-out complaints and documentation drafts; running tests, lint, type checks, the Python-only evaluation and the production build; fixing the defects those checks found |

### Files affected

- Backend: `complaint_processing/{sensitive,service}.py`, `knowledge_base/{ingestion,retrieval}.py`, `database/models/knowledge_base.py`, migration `*_document_safety.py`, `python_validation/checks.py`, `comparison_engine/{evaluate,labels}.py`, `sample_complaints/load_dataset.py`, `genai_pipeline/evidence.py`, `database/bootstrap.py`, `src/core/config.py`, `src/api/schemas.py`
- Configuration: `config/{detectors,validation}.yaml`, `deploy/railway/*.json`, `Makefile`, `requirements.txt`
- Data: `hidden_test_ready/holdout/*` (109 hand-written, labelled complaints)
- Frontend: knowledge-base table (quarantine warnings), regenerated API client
- Tests: `tests/security/test_adversarial.py`, `tests/integration/test_evaluation_pack.py`
- Docs: `documentation/*`, `README.md`

### Changes made

- Sensitive-data redaction at intake; quarantine of policy passages that instruct the AI; a global list of never-allowed actions; broader refund and compensation promise patterns.
- A security suite covering all eight SRS attacks, and the Security Testing Report.
- A hold-out set written separately from the dataset generator, an evaluator-pack importer and an evaluation command with per-complaint timing against the 20-second target.
- Production configuration checks, Railway service definitions, a one-command database bootstrap and a deployment guide.
- Project report with diagrams, user and evaluator guides, evaluation write-up, test-case map, blog draft, demo script and contribution template.

### Issues found and fixed during the session

- The security tests showed that a reply promising "50% of the price back" was not recognised as a promise, and that a policy exception proposed by the GenAI was only blocked when a rule listed it.
- The hold-out evaluation showed 9 missed escalations (safety, privacy, account takeover) caused by lexicon gaps such as "sparked", "smelled burnt", "it wasn't me"; the lexicons were extended, the dataset re-checked for regressions, and both results are reported in `documentation/evaluation.md`.
- The evaluation tests showed that evaluator packs needed `created_at` and that labels were read only from the repository, not from the pack; both fixed.
- `requirements.txt` had not been regenerated after Day 4's new libraries.

### Tests performed

- 256 automated backend tests pass (including 26 security tests and the evaluator-pack test); ruff, mypy `--strict`, ESLint, `tsc` and `next build` pass.
- Python-only evaluation on the 108 accepted hold-out complaints: category 66.7% (100% when the classifier is confident), escalation agreement 94.4% with no missed escalations.
- Not yet run: the GenAI evaluation and latency measurement, evidence export and deployment (they need the API key and hosting accounts).

### Verified by

| Team member | Modules reviewed | Date |
|---|---|---|
| _to be completed by the team_ | | |

## Entry 6: OpenAI as a second GenAI provider

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Let the team switch the GenAI provider between Claude and OpenAI with one setting |
| **Type of assistance** | Code generation and tests; checking the installed OpenAI SDK (3.19.2) types before writing the adapter |

- **Files affected:** `genai_pipeline/providers.py`, `src/core/config.py`, `genai_pipeline/analyze.py`, `comparison_engine/evaluate.py`, `.env.example`, `Makefile`, `pyproject.toml`, `uv.lock`, `requirements.txt`, `tests/unit/test_openai_provider.py`, `README.md`, `documentation/{deployment,project_report}.md`.
- **Changes made:** `GENAI_PROVIDER=anthropic|openai`; separate model and key per provider (`GENAI_MODEL` still sets the Claude model); an OpenAI adapter using the Responses API with strict JSON-schema output, mapping refusals, truncation and errors onto the pipeline's common types.
- **Tests performed:** 11 new tests against a mocked HTTP transport (request shape, strict schema, reasoning on/off, refusal, truncation, transient and permanent errors, provider selection); full suite, ruff and mypy pass. Not yet run against the live OpenAI API (no key configured).
- **Verified by:** _to be completed by the team_

## Entry 7: Demo shop and support chat

| Field | Details |
|---|---|
| **Date** | 2026-09-26 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Add a VoltHaven demo shop and a guided support chat that files complaints through the existing pipelines and posts the validated reply |
| **Type of assistance** | Design (spec and plan in `docs/superpowers/`), code generation, tests, browser checks |

- **Files affected:** `config/catalogue.yaml`, `database/models/{storefront,chat,complaints}.py`, two migrations, `storefront/**`, `support_chat/**`, `schemas/chat_intake.py`, `prompt_templates/chat_intake.yaml`, `genai_pipeline/output_schema.py`, `python_validation/pipeline.py`, `complaint_processing/review.py`, `src/api/routes/{storefront,chat}.py`, `src/api/schemas.py`, `src/main.py`, seeding and bootstrap, `web/src/app/(shop)/**`, `web/src/components/{shop,chat}/**`, `web/src/components/complaints/{chat-transcript,complaint-view}.tsx`, tests, docs.
- **Changes made:** product catalogue, checkout (one order per line, server prices, business-day delivery dates), order tracking, admin demo delivery outcomes; chat conversations with GenAI intake turns, a promise guard, fixed-question fallback, confirm-to-file using the customer's own words, and reply/holding/approval messages posted from validation and review.
- **Issues found and fixed:** inline YAML lists would have split specs such as "20,000 mAh"; a rollback after a rejected chat submission expired session objects (found by a test); the cart's first version failed the React hooks lint rule.
- **Tests performed:** 32 new backend tests (catalogue, checkout, delivery outcomes, intake turn, chat flow, replies); full suite, ruff, mypy, ESLint, tsc and `next build` pass; shop pages, cart and the chat panel checked in the browser (signed-in chat flow to be walked through by the team).
- **Verified by:** _to be completed by the team_

## Entry 8: Product management and worker fix

| Field | Details |
|---|---|
| **Date** | 2026-09-27 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Let administrators manage shop products and images; fix background tasks on macOS; show chat messages immediately |

- **Files affected:** `database/models/storefront.py`, migration `*_product_images.py`, `storefront/{catalogue,images}.py`, `src/api/routes/storefront.py`, `src/api/schemas.py`, `web/src/components/settings/{products-manager,product-images}.tsx`, `web/src/components/shop/product-image.tsx` and the shop pages, `web/src/app/(app)/settings/products/page.tsx`, sidebar, chat panel, `Makefile`, tests, docs.
- **Changes made:** product create/edit/hide and up to 5 content-checked images per product with ordering, served with long-lived caching; images in the shop, cart and orders; catalogue seeding no longer overwrites admin edits. `make worker` uses a threads pool: on macOS the default pool spawns child processes in which Celery's task table is empty, so every task failed. The chat now shows the customer's message as soon as it is sent.
- **Tests performed:** 9 new integration tests (admin-only access, create/edit/hide, hidden products blocked at checkout, upload/order/serve/delete, invalid and oversized files, 5-image limit, seed not overwriting edits, order images); full suite 322 passed; ruff, mypy, ESLint, tsc and `next build` pass; image display checked in the browser; the worker fix verified by running an SLA scan on a threads-pool worker.
- **Verified by:** _to be completed by the team_

## Entry 9: Storefront redesign, Contact us and enquiries

| Field | Details |
|---|---|
| **Date** | 2026-09-27 |
| **Tool** | Claude Code (Anthropic), model Claude Opus 5.5 |
| **Purpose** | Make the demo shop look and behave like a real e-commerce site, add Contact us (a web-form complaint channel) and a staff enquiries inbox |

- **Files affected:** `config/storefront.yaml`, `storefront/{config,queries,orders}.py`, `support_contact/`, `database/models/contact.py`, migration `*_contact_and_newsletter.py`, `security/dependencies.py` (optional sign-in), `src/api/routes/{storefront,contact}.py`, `src/api/schemas.py`, `web/src/components/{motion,shop,enquiries}/`, the shop pages under `web/src/app/(shop)/`, `web/src/app/(app)/enquiries/`, `web/src/app/not-found.tsx`, `web/src/proxy.ts`, sidebar, docs.
- **Changes made:** shop facts (company, delivery, returns, warranty, FAQ) in one config served by `GET /storefront/config`; checkout delivery days now follow the Delivery Policy (standard 5, express 2 business days; previously 3 and 1); product search, price range and sorting including best sellers from real orders; `POST /contact` routes order problems into the normal complaint intake and other topics into redacted enquiries (honeypot for bots); staff enquiries inbox with mark handled and convert to complaint; idempotent newsletter sign-up. New site: header with category menu, search suggestions and slide-in cart, animated home page, filterable shop, product gallery with zoom and delivery estimate, restyled cart, checkout with confirmation and orders with a timeline, About, Contact, Help centre, Shipping, Returns, Warranty, Privacy, Terms, 404, light/dark theme; all motion respects reduced-motion settings.
- **Tests performed:** 28 new backend tests (policy figures vs knowledge-base documents, catalogue queries incl. literal search of SQL wildcard characters, contact routing, redaction incl. complaint titles, short first lines, duplicates, foreign orders, staff-only inbox, conversion rules, audit events, newsletter); full suite 350 passed; ruff, mypy, ESLint, tsc and `next build` pass; pages checked in the browser at desktop and phone widths and in dark mode.
- **Verified by:** _to be completed by the team_

