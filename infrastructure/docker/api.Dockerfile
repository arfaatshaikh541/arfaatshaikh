# GRIDKEEP API — FastAPI backend
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Installed outside /app deliberately: docker-compose.yml bind-mounts
# ./apps/api onto /app for the dev hot-reload loop, which replaces the
# whole directory at container start — including anything installed
# under /app during the image build that isn't part of ./apps/api on
# the host. Keeping the connector SDK's editable install rooted outside
# that mount means it survives it (worker.Dockerfile already does this,
# installing it at /app/packages/connector-sdk, outside the directories
# its own volumes mount).
WORKDIR /opt/connector-sdk
COPY packages/connector-sdk/ ./
RUN pip install --no-cache-dir -e .

WORKDIR /app
COPY apps/api/ ./
RUN pip install --no-cache-dir -e ".[dev]"

RUN useradd --create-home --uid 1000 gridkeep \
    && chown -R gridkeep:gridkeep /app /opt/connector-sdk
USER gridkeep

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
