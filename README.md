# SupportNova

**Complaint resolution intelligence for VoltHaven Electronics** (a fictional consumer-electronics
e-commerce company). A Generative AI pipeline analyses each customer complaint; an independent
Python ground-truth pipeline validates every recommendation against the Complaint Resolution
Rule Matrix and approved, versioned company policy before anything reaches a customer.

> Status: **Day 2 of 5**. Complaint intake, the Complaint Resolution Rule Matrix (111 rules), the
> GenAI Complaint Intelligence Pipeline and the 536-complaint labelled dataset are complete. The
> Python Ground-Truth Validation Pipeline, comparison engine and manual review come on Day 3.

## Architecture

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
| Jobs | Celery + Redis (document ingestion, complaint analysis; SLA scans later) |
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
| `python_validation/`, `comparison_engine/`, `hallucination_checks/` | Day 3 modules |

## Local setup

**Prerequisites:** Docker Desktop, [uv](https://docs.astral.sh/uv/) (`brew install uv`),
Node.js 24 and pnpm (`brew install pnpm`). uv installs Python 3.13 automatically.

```bash
cp .env.example .env                  # backend settings
cp web/.env.example web/.env.local    # frontend settings (Clerk keys)
make setup                            # uv sync + pnpm install
make infra                            # PostgreSQL 18 + pgvector, Redis 8
make migrate seed                     # schema, taxonomy, SLAs, rule matrix
make import-docs                      # build and ingest the 20 policy documents
make load-dataset                     # 504 customers, 404 orders, 536 complaints
```

Run each in its own terminal:

```bash
make api      # http://localhost:8000/docs
make worker   # Celery worker for uploads
make web      # http://localhost:3000
```

`make help` lists every task. Everything also runs in containers with
`docker compose --profile app up`.

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
make test     # 170 backend tests (needs `make infra`; uses the supportnova_test database)
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

## Assumptions and limitations (so far)

- VoltHaven Electronics, its customers, policies and complaints are fictional.
- Scanned (image-only) PDFs are rejected with a clear message; OCR is out of scope.
- DOCX files have no fixed pagination, so their chunks carry section references but no page numbers.
- Business-day calculations ignore public holidays.
- The GenAI pipeline has been tested with a scripted provider; live runs need an Anthropic API key
  (latency against the 20-second target is measured once the key is configured).
