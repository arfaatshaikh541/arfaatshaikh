# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY apps/api/pyproject.toml apps/api/uv.lock* /app/apps/api/
WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY apps/api /app/apps/api
COPY packages/connector-sdk /app/packages/connector-sdk
COPY packages/scoring-contracts /app/packages/scoring-contracts

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
