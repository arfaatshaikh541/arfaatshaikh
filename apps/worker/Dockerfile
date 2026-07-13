FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api /srv/apps/api
COPY apps/worker /srv/apps/worker

RUN pip install --no-cache-dir -e /srv/apps/api \
    && pip install --no-cache-dir -e /srv/apps/worker

WORKDIR /srv/apps/worker

CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info"]
