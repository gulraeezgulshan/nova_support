# One image for the API, Celery worker and Celery beat (different start commands).
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
# No cache mount: Railway's builder only accepts cache mounts with a service-specific id.
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    FASTEMBED_CACHE_PATH=/app/.models
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
# Download the embedding model at build time, so containers start without network access.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers"]
