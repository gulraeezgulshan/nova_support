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
