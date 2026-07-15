# GRIDKEEP Celery worker. Reuses apps/api's core/db/modules packages
# directly (see apps/worker/celery_app.py) — both are copied into the
# image preserving their relative apps/ layout.
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/apps

COPY apps/api/ ./api/
COPY apps/worker/ ./worker/

RUN pip install --no-cache-dir -e "./api[dev]"

RUN useradd --create-home --uid 1000 gridkeep && chown -R gridkeep:gridkeep /app
USER gridkeep

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD celery -A worker.celery_app inspect ping -t 5 || exit 1

CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info"]
