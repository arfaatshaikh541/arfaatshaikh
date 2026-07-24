# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

WORKDIR /src

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

RUN groupadd --system --gid 65532 policyengine \
    && useradd --system --uid 65532 --gid policyengine --no-create-home policyengine

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
USER policyengine

EXPOSE 8090

ENTRYPOINT ["python", "-m", "policy_engine"]
