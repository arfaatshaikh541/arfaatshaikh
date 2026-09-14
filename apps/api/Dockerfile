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
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
USER app
EXPOSE 8000

# SECURITY: --forwarded-allow-ips must never be "*" in production. With a
# wildcard, uvicorn trusts an X-Forwarded-For header from ANY connecting
# client, letting an attacker spoof their own source IP on every request and
# bypass IP-keyed rate limiting (app/core/rate_limit.py) entirely - e.g. a
# scripted brute-force against /api/v1/auth/login with a fresh fake IP per
# attempt. Set WOI_FORWARDED_ALLOW_IPS to the exact address (or CIDR, on
# uvicorn versions that support it) of your reverse proxy; the default here
# trusts nothing but loopback, so an unconfigured deployment fails closed
# (degraded per-proxy-IP rate-limit granularity) rather than open.
ENV WOI_FORWARDED_ALLOW_IPS="127.0.0.1"
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="$WOI_FORWARDED_ALLOW_IPS"
