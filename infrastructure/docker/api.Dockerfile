# GRIDKEEP API — FastAPI backend
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/connector-sdk/ ./connector-sdk/
RUN pip install --no-cache-dir -e "./connector-sdk"

COPY apps/api/ ./
RUN pip install --no-cache-dir -e ".[dev]"

RUN useradd --create-home --uid 1000 gridkeep && chown -R gridkeep:gridkeep /app
USER gridkeep

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
