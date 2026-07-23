# Local Development

## Known environment limitation (read this first)

The Docker Compose stack (`docker-compose.yml` at the repo root) defines Postgres, Redis,
Redpanda, MinIO, Vault (dev mode), and Mailpit. Its syntax is validated
(`docker compose config -q` passes), but in the sandboxed session this repository was built
in, `docker compose up` could not be fully runtime-validated: the environment's egress policy
blocks Docker Hub's image CDN (`production.cloudfront.docker.com` returns 403). This is an
environment/network policy limitation, not a defect in the compose file.

Instead, this Milestone was built and tested against **natively installed** PostgreSQL 16 and
Redis (already present in that sandbox), which are functionally equivalent to the Compose
services for everything the control-api/worker actually use. In a normal developer machine or
CI runner with real Docker Hub access, `docker compose up -d` should work as written -- this
has not been executed end-to-end and should be the first thing verified in an environment with
registry access.

## Prerequisites

- Go 1.25+
- Node.js 22+
- Python 3.12+
- PostgreSQL 16 (native, or via `docker compose up -d postgres`)
- Redis 7 (native, or via `docker compose up -d redis`)
- An SMTP endpoint for local email capture -- either Mailpit (`docker compose up -d mailpit`,
  UI at http://localhost:8025) or, in an environment without Docker registry access,
  `python3 -m smtpd -n -c DebuggingServer localhost:1025` (prints captured mail to stdout;
  labeled dev-only, never a real relay).

## First-time setup

```bash
cp .env.example .env
# Edit MFA_ENCRYPTION_KEY to a real value: openssl rand -base64 32

createuser gridkeep --pwprompt   # or via docker compose
createdb gridkeep --owner gridkeep
createdb gridkeep_test --owner gridkeep
```

## Running control-api

```bash
cd apps/control-api
go build -o /tmp/control-api-bin ./cmd/server
DATABASE_URL="postgres://gridkeep:gridkeep_dev_password@localhost:5432/gridkeep?sslmode=disable" \
REDIS_URL="redis://localhost:6379/0" \
MFA_ENCRYPTION_KEY="$(openssl rand -base64 32)" \
PKI_CA_ENCRYPTION_KEY="$(openssl rand -base64 32)" \
CONTROL_API_ENV=development CONTROL_API_PORT=8080 SESSION_COOKIE_SECURE=false \
CORS_ALLOWED_ORIGINS=http://localhost:3000 SMTP_HOST=localhost SMTP_PORT=1025 \
/tmp/control-api-bin
```

Migrations run automatically on startup (embedded, idempotent via `schema_migrations`).

## Seeding fictional demo data

```bash
cd apps/control-api
go build -o /tmp/seed-bin ./cmd/seed
DATABASE_URL="postgres://gridkeep:gridkeep_dev_password@localhost:5432/gridkeep?sslmode=disable" \
CONTROL_API_ENV=development /tmp/seed-bin
```

Safe to re-run (idempotent). See `docs/project-status.md` for the seeded demo credentials.

## Running the worker

```bash
cd apps/worker
go build -o /tmp/worker-bin ./cmd/worker
KAFKA_BROKERS=localhost:19092 WORKER_CONSUMER_GROUP=gridkeep-worker-dev /tmp/worker-bin
```

Note: this requires a real Kafka-API broker (Redpanda). It was **not** runtime-validated in
this session for the same Docker registry reason described above; its unit tests
(`internal/consumer`) validate the idempotent-consumer/retry/dead-letter logic against fakes
and pass, but the live `kafka-go` client has not been exercised against a live broker here.

## Running policy-engine

```bash
cd apps/policy-engine
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m policy_engine   # serves on :8090, GET /health
```

## Running web

```bash
cd apps/web
npm install
NEXT_PUBLIC_CONTROL_API_URL=http://localhost:8080 npm run dev   # http://localhost:3000
```

## Running tests

```bash
# control-api (requires TEST_DATABASE_URL pointing at gridkeep_test; see ADR 0005 for -p 1)
cd apps/control-api
TEST_DATABASE_URL="postgres://gridkeep:gridkeep_dev_password@localhost:5432/gridkeep_test?sslmode=disable" \
go test -p 1 ./...

# worker
cd apps/worker && go test ./...

# policy-engine
cd apps/policy-engine && source .venv/bin/activate && python -m pytest -q

# web
cd apps/web && npx vitest run
```
