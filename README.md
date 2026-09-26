# SupportNova

**Complaint resolution intelligence for VoltHaven Electronics** (a fictional consumer-electronics
e-commerce company). A Generative AI pipeline analyses each customer complaint; an independent
Python ground-truth pipeline validates every recommendation against the Complaint Resolution
Rule Matrix and approved, versioned company policy before anything reaches a customer.

> Status: **Day 1 of 5**. Platform foundation, authentication/RBAC, configurable taxonomy and the
> knowledge-base pipeline are complete. Complaint analysis (GenAI + validation) starts Day 2.

## Architecture

```
Browser ─► Next.js 16 (web/) ──Bearer token (Clerk)──► FastAPI (src/) ──► PostgreSQL 18 + pgvector
                                                         │                 Redis 8 ◄─► Celery worker
                                                         └─► Claude API (Day 2)
```

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query, typed client generated from OpenAPI (@hey-api/openapi-ts) |
| Auth | Clerk (identity) + SupportNova roles in PostgreSQL (authorisation, enforced by FastAPI) |
| Backend | Python 3.13, FastAPI, Pydantic 2, SQLAlchemy 2.1 (async), Alembic |
| Jobs | Celery + Redis (document ingestion; batch analysis, SLA scans later) |
| Knowledge base | PyMuPDF (PDF), python-docx (DOCX), section-aware chunking, fastembed (`bge-small-en-v1.5`), hybrid pgvector + full-text retrieval |
| GenAI | Anthropic Claude API, structured JSON output (Day 2) |
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
| `config/` | Organisation profile, taxonomy (12 categories, 38 subcategories, 10 departments), SLAs, document categories |
| `sample_documents/` | Policy sources (`sources/*.md`) and generated PDF/DOCX/MD files |
| `tests/` | Unit and integration tests |
| `web/` | Next.js frontend |
| `genai_pipeline/`, `python_validation/`, `complaint_rules/`, `routing_rules/`, `escalation_rules/`, `prompt_templates/`, `schemas/`, `comparison_engine/`, `hallucination_checks/`, `complaint_processing/` | Placeholders for Day 2–3 modules |

## Local setup

**Prerequisites:** Docker Desktop, [uv](https://docs.astral.sh/uv/) (`brew install uv`),
Node.js 24 and pnpm (`brew install pnpm`). uv installs Python 3.13 automatically.

```bash
cp .env.example .env                  # backend settings
cp web/.env.example web/.env.local    # frontend settings (Clerk keys)
make setup                            # uv sync + pnpm install
make infra                            # PostgreSQL 18 + pgvector, Redis 8
make migrate seed                     # schema + taxonomy
make import-docs                      # build and ingest the sample policies
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
make test     # 71 backend tests (needs `make infra`; uses the supportnova_test database)
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
- Complaint text and uploaded documents are treated as untrusted data (prompt-injection defences
  arrive with the GenAI pipeline on Day 2).

## Assumptions and limitations (so far)

- VoltHaven Electronics, its customers, policies and complaints are fictional.
- Scanned (image-only) PDFs are rejected with a clear message; OCR is out of scope.
- DOCX files have no fixed pagination, so their chunks carry section references but no page numbers.
- 7 of the 20+ required knowledge-base documents exist so far; the rest are added on Day 2.
