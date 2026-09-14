FROM python:3.12-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/
WORKDIR /app
COPY apps/api/pyproject.toml ./
RUN uv sync --no-dev

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY apps/api/app ./app
COPY apps/worker/worker ./worker
USER app
CMD ["celery", "-A", "worker.celery_app:celery_app", "worker", "--loglevel=INFO", "--without-gossip", "--without-mingle"]
