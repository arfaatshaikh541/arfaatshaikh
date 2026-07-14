FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The worker re-uses the api package's modules (service-layer functions),
# so it depends on the api package directly rather than duplicating code.
COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker

RUN pip install --upgrade pip \
    && pip install /app/apps/api \
    && pip install /app/apps/worker

WORKDIR /app/apps/worker

CMD ["celery", "-A", "app.celery_app", "worker", "--beat", "--loglevel=INFO"]
