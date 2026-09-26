# Common development tasks. Run `make help` for the list.
.PHONY: help setup infra migrate seed import-docs load-dataset bootstrap analyze triage-python reports sla-scan report-baseline report-comparison evaluate evaluate-python evidence final-evidence requirements api worker web test lint format openapi check

help:           ## Show this help
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

setup:          ## Install backend and frontend dependencies
	uv sync
	pnpm --dir web install

infra:          ## Start Postgres (pgvector) and Redis in Docker
	docker compose up -d --wait postgres redis

migrate:        ## Apply database migrations
	uv run alembic upgrade head

seed:           ## Load the taxonomy, SLAs and the rule matrix
	uv run python -m database.seed

import-docs:    ## Build and import the sample knowledge-base documents
	uv run python -m sample_documents.build_documents
	uv run python -m knowledge_base.import_documents sample_documents/generated/archive
	uv run python -m knowledge_base.import_documents sample_documents/generated

load-dataset:   ## Load the 536-complaint labelled dataset (customers, orders, complaints)
	uv run python -m sample_complaints.load_dataset

bootstrap:      ## Seed taxonomy and rules, import documents and load the dataset in one go (after migrate)
	uv run python -m database.bootstrap

analyze:        ## Analyse 10 unanalysed dataset complaints with the configured model (needs ANTHROPIC_API_KEY)
	uv run python -m genai_pipeline.analyze --limit 10

report-baseline: ## Python-only validation of the dataset, scored on its labels (no GenAI)
	uv run python -m comparison_engine.report baseline

report-comparison: ## GenAI vs Python comparison report for analysed complaints
	uv run python -m comparison_engine.report comparison

evaluate:       ## GenAI + Python on the 108 unseen hold-out complaints, with timing (needs ANTHROPIC_API_KEY)
	uv run python -m comparison_engine.evaluate hidden_test_ready/holdout

evaluate-python: ## Python-only evaluation of the hold-out pack (no GenAI, no database writes)
	uv run python -m comparison_engine.evaluate hidden_test_ready/holdout --python-only

evidence:       ## Export GenAI evidence (config, sample request/response, invalid outputs, retries)
	uv run python -m genai_pipeline.evidence

final-evidence: evaluate report-comparison reports evidence ## Everything that needs the API key, in one go

requirements:   ## Regenerate requirements.txt from uv.lock
	uv export --no-dev --no-hashes --no-emit-project -o requirements.txt

api:            ## Run the FastAPI server (http://localhost:8000/docs)
	uv run uvicorn src.main:app --reload --port 8000

worker:         ## Run the Celery worker with the SLA scan scheduler (Beat) embedded
	uv run celery -A src.worker worker --beat --loglevel INFO -Q default,ingest,analysis --concurrency 2

triage-python:  ## Python-only validation of 100 unvalidated dataset complaints (no GenAI; all go to review)
	uv run python -m python_validation.triage --limit 100

reports:        ## Write the Complaint Intelligence Report (PDF, Excel, CSV) to reports/
	uv run python -m src.analytics.reports complaint_intelligence --format pdf xlsx csv

sla-scan:       ## Run one SLA risk scan now
	uv run python -m complaint_processing.sla

web:            ## Run the Next.js app (http://localhost:3000)
	pnpm --dir web dev

openapi:        ## Regenerate the typed frontend API client from the backend
	uv run python -m src.export_openapi
	pnpm --dir web api:generate

test:           ## Run backend tests
	uv run pytest

lint:           ## Lint and type-check backend and frontend
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy .
	pnpm --dir web lint
	pnpm --dir web typecheck

format:         ## Auto-format backend and frontend
	uv run ruff format .
	uv run ruff check . --fix
	pnpm --dir web format

check: lint test ## Everything CI runs
