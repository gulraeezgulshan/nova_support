# SupportNova

**Complaint resolution intelligence for VoltHaven Electronics** (a fictional consumer-electronics
e-commerce company). A Generative AI pipeline analyses each customer complaint; an independent
Python ground-truth pipeline validates every recommendation against the Complaint Resolution
Rule Matrix and approved, versioned company policy before anything reaches a customer.

| | |
|---|---|
| **Live application** | [supportnova-volthaven.vercel.app](https://supportnova-volthaven.vercel.app) — shop at `/`, staff console at `/dashboard` (evaluator credentials are in the submission form) |
| **Demonstration video** | _add the .mp4 link_ |
| **Technical blog** | [supportnova-volthaven.vercel.app/blog/letting-the-model-talk](https://supportnova-volthaven.vercel.app/blog/letting-the-model-talk) (source: [web/content/blog/](web/content/blog/letting-the-model-talk.md)) |

A demo VoltHaven shop (search, filters, cart, checkout without payment, order tracking, help
and policy pages, Contact us) and a guided support chat that file complaints through both
pipelines sit on top of the SRS scope. Contact-form messages that are not complaints go to a
staff **Enquiries** inbox. Complaints also arrive **by e-mail** (a real mailbox checked every
minute, with replies sent back in the same thread) and by **bulk upload** (CSV/Excel), and
customers can attach **supporting documents** (photos, PDFs) — the SRS intake channels.

All five days are complete: intake, knowledge base, rule matrix (111 rules), GenAI pipeline,
Python ground-truth validation, comparison, manual review, SLA tracking, dashboards,
analytics, reports, security hardening, evaluation tooling and deployment configuration.

## Documentation

| Document | Contents |
|---|---|
| [Project report](documentation/project_report.md) | Problem, requirements, architecture, database design, DFD, use-case, activity and sequence diagrams, pipelines, prompt, schema, validation, security, limitations |
| [User guide](documentation/user_guide.md) | Execution instructions: login, documents, rules, submitting, analysis, validation, review, escalation, tracking, analytics, reports |
| [Evaluator guide](documentation/evaluator_guide.md) | Hidden data, policy update, new category, traps, live modifications, deliberate defects |
| [Evaluation](documentation/evaluation.md) | Unseen hold-out set, GenAI vs Python comparison, Python accuracy, latency |
| [Security testing report](documentation/security_testing_report.md) | Adversarial tests and results |
| [Test cases](documentation/test_cases.md) | SRS test categories mapped to the 449 automated tests |
| [Deployment](documentation/deployment.md) | Vercel, Railway, Cloudflare R2, Clerk, evaluator accounts |
| [Demo script](documentation/demo_script.md), [team contributions](documentation/team_contributions.md), [AI usage](AI_USAGE.md) | Submission material |

## Architecture

Full diagrams (editable source: [documentation/architecture.drawio](documentation/architecture.drawio),
open it at app.diagrams.net):

| Page | Shows |
|---|---|
| [1 · Architecture overview](documentation/diagrams/1-architecture-overview.png) | Users, intake channels, web app, API, worker and scheduler, data stores and external services |
| [2 · Complaint lifecycle](documentation/diagrams/2-complaint-lifecycle.png) | One complaint from intake through Pipeline 1 (GenAI) and Pipeline 2 (Python) to reply, review, SLA and reports |
| [3 · Knowledge base & RAG](documentation/diagrams/3-knowledge-base-rag.png) | Document ingestion, versions, hybrid retrieval and citation checks |
| [4 · Deployment, CI & security](documentation/diagrams/4-deployment-ci-security.png) | Vercel + Railway services, CI checks and security controls |

![SupportNova architecture overview](documentation/diagrams/1-architecture-overview.png)

```
Browser ─► Next.js 16 (web/) ──Bearer token (Clerk)──► FastAPI (src/) ──► PostgreSQL 18 + pgvector
                                                         │                 Redis 8 ◄─► Celery worker
                                                         └─► Claude API (structured JSON)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query, typed client generated from OpenAPI (@hey-api/openapi-ts) |
| Auth | Clerk (identity) + SupportNova roles in PostgreSQL (authorisation, enforced by FastAPI) |
| Backend | Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2.1 (async), Alembic |
| Jobs | Celery + Redis (document ingestion, complaint analysis and validation), Celery Beat (SLA risk scan every 5 minutes) |
| Knowledge base | PyMuPDF (PDF), python-docx (DOCX), section-aware chunking, fastembed (`bge-small-en-v1.5`), hybrid pgvector + full-text retrieval |
| GenAI | Anthropic Claude API (`claude-opus-5`, configurable), JSON-schema structured outputs, prompt caching, server-side refusal fallbacks |
| Quality | pytest, Ruff, mypy (strict), ESLint, Prettier, GitHub Actions, gitleaks |

**Design rules**

- The GenAI model *proposes*; Python rules *decide*. The model never approves refunds, routing,
  escalation or policy precedence on its own.
- Categories, departments, SLAs and document categories are **data**, editable at runtime, so new
  categories or rules in the hidden evaluation pack need no code change.
- Only the **active** version of each policy can be retrieved; superseded, previous and draft
  versions are kept for traceability but never used as a resolution basis.
- Every retrieved passage is traceable: document ID, version, section, heading and page
  (chunk codes look like `DEL-POL-04@2.0#007`).
- Every change is written to an append-only audit trail.

## Repository layout

The top-level folders follow the SRS deliverable structure.

| Folder | Contents |
|---|---|
| `src/` | FastAPI app (`main.py`), API routes and schemas, settings, storage, Celery app |
| `database/` | ORM models, sessions, audit helpers, seed script, Alembic migrations |
| `security/` | Clerk token verification, user provisioning, RBAC dependencies |
| `document_processing/` | File validation, PDF/DOCX/TXT/MD parsing, chunking |
| `knowledge_base/` | Ingestion, versioning rules, embeddings, hybrid retrieval, bulk importer |
| `complaint_processing/` | Intake validation, sanitisation, entity extraction, risk-signal detectors, rule facts |
| `complaint_rules/` | Rule Matrix CSV (79 resolution rules), safe condition language, rule engine, matrix loader |
| `escalation_rules/` | 32 escalation rules that apply to every complaint, whatever its category |
| `routing_rules/` | Department severity order and category defaults (mirrors RTG-RUL-01) |
| `genai_pipeline/` | Pipeline 1: vocabulary, JSON schema, prompt registry, provider adapter, validation, retries |
| `prompt_templates/` | Versioned prompt templates (YAML) |
| `schemas/` | The GenAI output contract (`complaint_analysis.v1`) |
| `config/` | Organisation, taxonomy, SLAs, analysis vocabularies, action codes, detector lexicons |
| `sample_documents/` | 20 policy/SOP/FAQ documents + 1 archived version (sources and PDF/DOCX/MD) |
| `sample_complaints/` | Dataset generator, 536 labelled complaints, 504 customers, 404 orders, loader |
| `tests/` | Unit and integration tests |
| `web/` | Next.js frontend |
| `python_validation/` | Pipeline 2: independent classifier, 19 checks, scoring, verdicts, review tasks |
| `hallucination_checks/` | Unsupported-promise and untraceable-fact detection in drafted responses |
| `comparison_engine/` | GenAI vs Python comparison report and the Python-only baseline |
| `src/analytics/` | Dashboards and analytics queries, trend detection, report builders and CSV/Excel/PDF exporters |
| `reports/` | Generated reports |
| `hidden_test_ready/` | Unseen evaluation packs (`holdout/`: 109 hand-written, labelled complaints) |
| `email_channel/`, `bulk_import/` | E-mail complaints (parsing, processing, outbox, mailbox check) and bulk CSV/Excel upload |
| `storefront/`, `support_chat/`, `support_contact/` | Demo shop (catalogue queries, checkout, orders, shop facts from `config/storefront.yaml`), the support chat, and Contact us / enquiries / newsletter |
| `deploy/` | Railway service configuration (api, worker, beat) |
| `documentation/` | Project report, guides, evaluation, security report, test cases, blog draft, demo script |

## Local setup

**Prerequisites:** Docker Desktop, [uv](https://docs.astral.sh/uv/) (`brew install uv`),
Node.js 24 and pnpm (`brew install pnpm`). uv installs Python 3.13 automatically.

```bash
cp .env.example .env                  # backend settings
cp web/.env.example web/.env.local    # frontend settings (Clerk keys)
make setup                            # uv sync + pnpm install
make infra                            # PostgreSQL 18 + pgvector, Redis 8
make migrate                          # database schema
make bootstrap                        # taxonomy, SLAs, 111 rules, 20 documents, 536 complaints
```

(`make seed`, `make import-docs` and `make load-dataset` run the same steps one at a time.)

Run each in its own terminal:

```bash
make api      # http://localhost:8000/docs
make worker   # Celery worker (uploads, analysis) with the SLA scan scheduler
make web      # http://localhost:3000
```

`make help` lists every task. Everything also runs in containers with
`docker compose --profile app up`.

### Installation details

- **Python**: uv installs Python 3.13 and creates the virtual environment in `.venv` on
  `make setup` (`uv sync`). Without uv: `python3.13 -m venv .venv`,
  `source .venv/bin/activate`, `pip install -r requirements.txt`.
- **GenAI API**: Claude (Anthropic) or OpenAI, chosen by one line in `.env`:
  `GENAI_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`, or
  `GENAI_PROVIDER=openai` with `OPENAI_API_KEY` and `OPENAI_MODEL` (any model with
  JSON-schema structured outputs; `OPENAI_REASONING=false` for models without reasoning
  effort). Keys go in `.env` only, never in `.env.example` or any committed file. Without
  a key the app runs; complaints are validated by Python alone and go to manual review.
  Both providers get the same prompt and JSON schema, and every analysis records the
  provider and model that produced it.
- **Database**: `make infra` starts PostgreSQL with pgvector and Redis in Docker; `DATABASE_URL`
  and `REDIS_URL` in `.env` point elsewhere if needed.
- **Hold-out evaluation pack**: `uv run python -m database.bootstrap --with-holdout`.
- **Tests**: `make test` (creates and uses the `supportnova_test` database).

### Troubleshooting

| Symptom | Fix |
|---|---|
| "SupportNova API is unavailable … 401 Invalid session token" | `CLERK_ISSUER` in `.env` is not your Clerk Frontend API URL; fix it and restart `make api` |
| "Cannot reach the API" | `make api` is not running, or `NEXT_PUBLIC_API_URL` in `web/.env.local` is wrong |
| `Cannot connect to the Docker daemon` | Start Docker Desktop, then `make infra` |
| Complaints stay "Analysis queued" | Start `make worker` (and add `ANTHROPIC_API_KEY` for AI analysis) |
| Signed in but only customer screens | Your e-mail was not in `BOOTSTRAP_ADMIN_EMAILS` at first sign-in; an administrator changes the role under Users & roles |
| Charts missing after an update | Stop `make web` and start it again |
| YAML change has no effect | Restart `make api` and `make worker` (configuration is read at start-up) |

### Clerk configuration

1. Create an application at [dashboard.clerk.com](https://dashboard.clerk.com) (e-mail + password sign-in).
2. Copy the **Publishable key** and **Secret key** into `web/.env.local`.
3. Copy the **Frontend API URL** (e.g. `https://xyz.clerk.accounts.dev`) into `.env` as `CLERK_ISSUER`.
4. **Sessions → Customize session token**, add these claims so the API can create user records:
   ```json
   { "email": "{{user.primary_email_address}}", "name": "{{user.full_name}}" }
   ```
5. Put your own e-mail in `BOOTSTRAP_ADMIN_EMAILS` in `.env`; that account becomes an administrator
   on first sign-in. Other users start as customers; administrators change roles under
   **Users & roles**.
6. Deployed environments only: add a webhook to `https://<api-host>/api/v1/webhooks/clerk` for
   `user.created`, `user.updated` and `user.deleted`, and set `CLERK_WEBHOOK_SIGNING_SECRET`.

## Complaint analysis (Pipeline 1)

Submitting a complaint runs deterministic intake in Python first: validation (too short, bad or
foreign order references, unknown channels), sanitisation (hidden Unicode removed), entity
extraction, exact-duplicate rejection, and **risk signals** from the lexicons in
`config/detectors.yaml` (safety, injury, privacy, account compromise, legal threats, repeat
contact, prompt injection, policy claims, requested remedies). Then a Celery worker runs the
GenAI pipeline:

1. Retrieve the active policy passages for the complaint (hybrid search).
2. Render the versioned prompt (`prompt_templates/complaint_analysis.yaml`). Untrusted text
   is escaped so it cannot close the prompt's tags, and the model is told to treat
   instructions inside the complaint as data.
3. Call Claude with a JSON-schema constraint generated from the live taxonomy, so a new
   category or department added at runtime is accepted on the next analysis.
4. Validate the JSON in Python: types, valid codes, subcategory-to-category pairing, action
   codes, and policy citations that must be among the retrieved passages.
5. If the output is invalid, retry once with the errors. If it is still invalid (or the model
   refused, or the provider is down), the complaint is flagged for **manual review** and
   the invalid output is never used.

Every run records prompt name/version/hash, provider, model, schema version, policy passages,
attempts, tokens and latency; every model call stores its request and raw response.

```bash
# needs ANTHROPIC_API_KEY in .env
uv run python -m genai_pipeline.analyze --limit 10
uv run python -m genai_pipeline.analyze --refs CMP-000012 CMP-000040
```

## Complaint Resolution Rule Matrix

`complaint_rules/rule_matrix.csv` (resolution rules per category/subcategory) and
`escalation_rules/escalation_rules.csv` (rules that apply to any complaint) are seeded into
the database and editable at runtime through the API (`/api/v1/rules`). Conditions use a
small, safe expression language over Python-computed facts (see `complaint_rules/facts.py`):

```
days_late > 5 and shipping_method == 'standard'
safety_hazard or 'SAFETY' in issue_categories
order_amount > 1000 and (requests_refund or requests_compensation)
```

Conditions are parsed with Python's `ast` against a whitelist (never `eval`). Unknown facts,
action codes, departments or malformed policy references are rejected on save. A test proves
every policy reference in the matrix points to a real section of a real document.

## Ground-truth validation (Pipeline 2)

After every GenAI analysis (and whenever the GenAI is unavailable), Python validates the
recommendation **without using any AI**. The GenAI output is input to be checked, never a
source of truth.

1. **Independent classification.** `python_validation/classifier.py` scores the complaint
   against weighted keyword patterns per subcategory (`config/classification.yaml`) plus the
   deterministic risk signals. It reports `confident`, `tentative` or `unknown` instead of
   guessing, and safety and privacy win whenever they are confidently present.
2. **Rules.** The rule matrix and all escalation rules are applied to Python-computed facts to
   get the expected department, supporting departments, urgency, priority, escalation level,
   required and prohibited actions, and the policy sections to cite.
3. **Checks** (`python_validation/checks.py`), each with a status (pass / warn / fail / skip),
   a severity and evidence:

   | Area | What is checked |
   |---|---|
   | Structure | Schema and vocabulary; subcategory belongs to category |
   | Classification | Category, subcategory, department, supporting departments |
   | Risk | Urgency, priority, escalation (never lower than the rules require) |
   | Actions | Required actions present, prohibited actions absent |
   | Compensation | Type allowed for the category, within the policy cap (e.g. store credit at most 10% of the order and USD 50) |
   | Policy | Citations point to active versions only; required sections cited |
   | Response | Unsupported promises (refunds, deadlines, replacements not in the rules or policy), untraceable facts (amounts, dates, order numbers not in the complaint, order or policy) |
   | Other | Contradictions, missing information, prompt injection handling, follow-up timing |

4. **Score and verdict.** Weighted score out of 100 (critical 5, major 3, minor 1; a warning
   counts half):
   - **Verified**: no failures, score at least 80.
   - **Verified with corrections**: Python safely enforced the rules itself (raised priority
     or escalation, added a mandatory action, added the supporting departments).
   - **Needs review**: anything a human must decide (wrong category, hallucinated facts,
     unsupported promises, compensation over the cap, invalid GenAI output, provider outage,
     escalation level 4 or 5, or a score below 80).

   The final complaint values keep the **more severe** of GenAI and Python, so a missed
   escalation is corrected even when the model got it wrong.

```bash
uv run python -m comparison_engine.report baseline     # Python only, scored on the dataset labels
uv run python -m comparison_engine.report comparison   # GenAI vs Python for analysed complaints
```

`reports/genai_python_comparison.csv` has the SRS columns (expected, GenAI and Python category,
department, urgency, priority, escalation, policy references, match, verification status and
an explanation of each difference). On the 531 loaded dataset complaints the Python-only
baseline scores category 94.9%, department 95.3%, urgency 97.0%, priority 97.0% and escalation
100% against the hand-set labels.

## Manual review, status and related complaints

- **Review queue** (reviewers, managers, administrators): every complaint with the verdict
  *Needs review*, with the reasons. One open task per complaint; new reasons are merged.
- **Reviewer actions**: approve, modify the response, reject, reclassify (the rules are
  re-applied), reassign, escalate (never lowered), regenerate the GenAI analysis, comment.
  Every decision stores the before and after state; the original GenAI and Python results are
  never overwritten, and everything goes to the audit trail.
- **Status lifecycle**: only allowed transitions (for example `new` cannot jump to
  `resolved`), each recorded as a complaint event with a customer-facing message.
- **Duplicates and repeats**: exact resubmissions are rejected; near-duplicates (fuzzy text
  match of at least 88%) and reworded repeats (embedding similarity of at least 0.80) are linked
  to the earlier complaint and shown on both.
- **Policy updates**: activating a new version of a document flags every open complaint whose
  latest analysis relied on the superseded version for review.

## SLA tracking

Response and resolution targets per priority live in the `sla_policies` table (edit them under
**Taxonomy & SLAs**). Deadlines are measured from submission and set as soon as a complaint has a
priority; they move if the priority changes.

| SLA status | Meaning |
|---|---|
| Awaiting triage | No priority yet (analysis pending) |
| On track | Open and inside both targets |
| At risk | Past the policy's at-risk share of a window (e.g. 75% of the resolution time) |
| Breached | Past the first-response or resolution deadline |
| Met / Missed | Resolved inside / after the resolution target |

The first response is the first move to assigned, in progress, awaiting customer, escalated or
resolved, or a reviewer approving the customer response. Celery Beat runs the SLA scan every
5 minutes (`config/analytics.yaml`); a complaint that becomes at risk or breached gets a
staff-only timeline entry and an audit event. `make sla-scan` runs one scan by hand.

## Dashboards, analytics and reports

| Who | Dashboard |
|---|---|
| Customer | Their complaints: ID, status, submitted date, department, latest update, resolution status |
| Agent | Open complaints for their department (or all), most urgent SLA first, with category, priority, sentiment, the GenAI summary and steps, validation result, suggested response and escalation warnings |
| Reviewer, manager, administrator | Totals, category, department, priority, escalation, resolution-status and SLA distributions, SLA risks, trends, GenAI/Python agreement and mismatches, manual-review cases |

**Analytics** covers volume over time (day, week or month), category, subcategory, product line,
department, urgency, sentiment, escalation level, channel, customer type, resolution time by
priority, department performance, repeat complaints and policy usage. Every view has the same
filters: date range, category, department, priority, sentiment and channel
(`src/analytics/filters.py`; adding a filter is one field, one clause and one query parameter).

**Trend detection** compares the last 7 days with the 7 days before and reports rising
categories (delivery and billing are always watched), recurring product issues (same product
line and subcategory at least 3 times), rising repeat complaints per department (repeated
service failures) and escalation spikes. Thresholds are in `config/analytics.yaml`.

**Reports** (screen **Reports**, or `uv run python -m src.analytics.reports <code> --format pdf xlsx csv`):

| Report | Contents |
|---|---|
| Complaint Intelligence | Category, priority and sentiment distribution, department routing, escalations, repeat complaints, SLA risk, policy usage, GenAI/Python disagreements, manual-review cases, trends |
| Complaint Analysis | Every complaint with its classification, plus breakdowns and weekly volume |
| Department Performance | Workload, escalations, SLA compliance and resolution time per department |
| Escalations | Escalated complaints by level |
| SLA Status | Running SLAs, risks, breaches, resolution time against target |
| Policy Usage | Documents retrieved, cited by the GenAI and required by the rules |
| Resolution Compliance | Whether resolved complaints were validated, signed off and on time |
| GenAI / Python Comparison | Field-by-field agreement with explanations |
| Manual Reviews | Review cases, reasons and reviewer decisions |

Each exports as **CSV** (UTF-8 with BOM, opens correctly in Excel), **Excel** (.xlsx, one sheet
per table, filters and frozen headers) or **PDF** (landscape A4, repeated table headers). The
filters on screen apply to the export.

**Search and filtering** in the complaint queue: reference, title or customer, status, priority,
sentiment, escalation, SLA status, date range and review flag. Administrators can add and edit
rules in the **Rule matrix** screen; every save is validated like the CSV import, versioned and
audited.

Without an API key, `make triage-python` validates 100 dataset complaints with Python only (as
happens during a GenAI outage), so the dashboards have data; every such complaint goes to
manual review, and a later GenAI analysis re-validates it.

## Labelled complaint dataset

`sample_complaints/generate_dataset.py` generates 536 complaints (523 unique + 5 intentional
exact duplicates + near-duplicates) from hand-written scenarios with expected labels
(category, department, urgency, priority, escalation, sentiment, clarification needed,
injection). It covers all 12 categories and 38 subcategories, plus multi-issue (including
three-issue), ambiguous/incomplete, contradictory-policy, outdated-policy, prompt-injection,
repeat, calm-but-critical, angry-but-low-risk, VIP-minor, low-value-privacy and legal-threat
cases. `labels.csv` lists the expected labels; a test checks that every label agrees with the
rule matrix.

## Knowledge-base documents

Upload PDF or DOCX (TXT and Markdown are also accepted) in the **Knowledge base** screen, or
bulk-import a folder:

```bash
uv run python -m knowledge_base.import_documents path/to/folder [--no-activate]
```

Metadata is read from the upload form or, when left blank, from header lines at the top of the
document:

```
Document ID: DEL-POL-04
Document Type: policy
Version: 2.0
Effective Date: 2026-01-01
Expiry Date: 2027-12-31
```

Validation rejects wrong or disguised file types, empty or oversized files, exact duplicates,
re-used version numbers, malformed document IDs, unknown document categories and invalid dates.
Uploading a new version of an existing document supersedes the previous active version once
processing succeeds.

Document categories and their precedence (lower number wins when sources conflict) live in
`config/knowledge_base.yaml`: compliance → policy / escalation / routing / SLA → SOP →
product guide → response template → FAQ. `FAQ-GEN-01` intentionally contradicts
`REF-POL-01` (refund timing, opened products) as a policy-conflict test case.

## Testing and quality

```bash
make test     # 449 backend tests (needs `make infra`; uses the supportnova_test database)
make lint     # ruff, mypy --strict, eslint, tsc
```

Integration tests run against real PostgreSQL + pgvector and sign Clerk-format tokens with a
local RSA key, so authentication, RBAC, webhook signatures, upload → ingest → activate → search
and version supersession are all tested without network access.

After changing API routes or schemas: `make openapi` regenerates the typed frontend client.

## Security notes

- API keys and secrets are read from environment variables only; `.env` files are git-ignored
  and CI runs a gitleaks secret scan.
- Bearer tokens are verified (RS256 signature, expiry, issuer, authorised party) on every request;
  roles are read from the database, never from the token.
- CORS is restricted to configured origins; uploads are type-checked by content, size-limited and
  stored under sanitised keys (path traversal is blocked).
- Complaint text is untrusted data: hidden characters are stripped at intake, markup is escaped
  inside the prompt, injection attempts are detected by Python and flagged for supervisor
  review, and the model's output can never approve anything by itself.
- Card numbers, security codes, passwords, PINs, ID and bank numbers are removed at intake,
  before storage or the GenAI; policy passages that try to instruct the AI are quarantined.
- Production refuses to start without a real Clerk issuer, a deployed CORS origin and object
  storage. Full results: [security testing report](documentation/security_testing_report.md).

## Evaluation, evidence and reports

```bash
make report-baseline   # Python-only accuracy on the 531 dataset complaints
make evaluate-python   # Python-only accuracy on the 108 unseen hold-out complaints
make evaluate          # GenAI + Python + latency on the hold-out (needs the API key)
make evidence          # GenAI evidence: config, sample request/response, invalid outputs, retries
make final-evidence    # everything that needs the API key, in one go
```

Evaluator packs: `uv run python -m comparison_engine.evaluate path/to/pack`
(see [the evaluator guide](documentation/evaluator_guide.md)).

## Assumptions

- VoltHaven Electronics, its customers, orders, policies and complaints are fictional.
- Orders are simulated records used to verify references and eligibility.
- Routing, urgency and priority are defined by the rule matrix; policies are the source for
  the rules, and a policy change is reflected by editing the matching rules.
- Complaints are in English.

## Limitations

- Scanned (image-only) PDFs are rejected with a clear message; OCR is out of scope.
- DOCX files have no fixed pagination, so their chunks carry section references but no page numbers.
- Business-day calculations ignore public holidays.
- The Python classifier and risk-signal lexicons are keyword-based: on unseen wording the
  classifier abstains more often (category check skipped rather than guessed) and unusual
  phrasings of a risk can be missed; the GenAI and reviewers are the next lines of defence
  (see [evaluation](documentation/evaluation.md)).
- Automated tests use a scripted GenAI provider; live accuracy and latency come from
  `make evaluate`.
- Responses are drafted and approved in the app but not sent to customers automatically.
