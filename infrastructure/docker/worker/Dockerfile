# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY apps/api/pyproject.toml apps/api/uv.lock* /app/apps/api/
WORKDIR /app/apps/api
RUN uv sync --frozen --no-dev || uv sync --no-dev

COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker
COPY packages/connector-sdk /app/packages/connector-sdk
COPY packages/scoring-contracts /app/packages/scoring-contracts

WORKDIR /app/apps/api

CMD ["uv", "run", "celery", "-A", "app.worker.celery_app", "worker", "--loglevel=INFO"]
