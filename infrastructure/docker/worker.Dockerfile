# GRIDKEEP Celery worker. Reuses apps/api's core/db/modules packages
# directly (see apps/worker/celery_app.py) — both are copied into the
# image preserving their relative apps/ layout.
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/connector-sdk/ ./packages/connector-sdk/
RUN pip install --no-cache-dir -e "./packages/connector-sdk"

WORKDIR /app/apps

COPY apps/api/ ./api/
COPY apps/worker/ ./worker/

RUN pip install --no-cache-dir -e "./api[dev]"

RUN useradd --create-home --uid 1000 gridkeep && chown -R gridkeep:gridkeep /app
USER gridkeep

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD celery -A worker.celery_app inspect ping -t 5 || exit 1

# Consumes every declared queue — see celery_app.ALL_QUEUE_NAMES. A
# production deployment wanting queue-level isolation (e.g. a dedicated,
# more tightly-limited pool for the `actions` queue per ADR-4) would
# instead run separate worker services each with a narrower `-Q`.
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "-Q", "default,sync,ingest,correlate,actions,reports"]
