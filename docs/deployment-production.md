# GRIDKEEP Cyber OS — Production Deployment Runbook

This is the operational counterpart to `docker-compose.production.yml`, added in Milestone 29 of the
production security hardening programme (see `docs/security-findings-register.md` for the specific
findings this closes). Read this before running the production overlay for the first time — the compose
file is written to fail loudly rather than silently misconfigure, and this document explains why each
required value exists and where to get it.

## What this repository provides, and what it deliberately does not

**Provided:** the application containers (`api`, `worker`, `beat`, `web`), their datastores
(`postgres`, `redis`, `object-storage`), and a production-mode Compose overlay
(`docker-compose.production.yml`) that hardens the defaults the base `docker-compose.yml` intentionally
leaves open for local development.

**Not provided, and out of this repository's scope:**

- **TLS termination.** Nothing in this repo terminates HTTPS. A real deployment needs a reverse proxy or
  cloud load balancer (nginx, Caddy, an AWS/GCP/Azure load balancer) in front of the `api` and `web`
  containers, configured with a real certificate. `Strict-Transport-Security` is sent unconditionally by
  the API (Milestone 29) — it has no effect until a real HTTPS listener exists in front of it.
- **Network segmentation beyond what `docker-compose.production.yml` already does** (removing host port
  publishing from `postgres`/`redis`/`object-storage`). Full network-topology segmentation (separate
  `data`/`public` Docker networks) is explicitly scoped to a later milestone in the hardening programme,
  not this one.
- **A production-grade secrets manager.** `VAULT_LOCAL_MASTER_KEY` below still uses the local
  envelope-encryption adapter — a real KMS-backed adapter is a separately tracked, not-yet-built
  milestone (finding C-02 in the findings register). Until it ships, treat `VAULT_LOCAL_MASTER_KEY` with
  the same handling rigor as a database root password.
- **A least-privilege database role.** As of this milestone, the application still connects to Postgres
  as a role with elevated privileges (finding C-01, tracked for a dedicated milestone). Do not treat
  Row-Level Security policies as an independent enforcement layer until that milestone ships and is
  verified — today, correct tenant isolation depends entirely on the application code, which is tested
  but not database-enforced.

## Before first boot: required environment variables

`docker-compose.production.yml` uses Compose's `${VAR:?message}` syntax for every value below — running
`docker compose -f docker-compose.yml -f docker-compose.production.yml config` without setting one of
these fails immediately with a specific, actionable error naming exactly which variable is missing. This
is intentional: a production deployment should fail before any container starts, not after.

| Variable | What it is | How to generate a real value |
|---|---|---|
| `POSTGRES_PASSWORD` | Database password for the `gridkeep` role | `openssl rand -base64 32` |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | Object-storage admin credentials | A real username; `openssl rand -base64 32` for the password |
| `DATABASE_URL` | `postgresql+asyncpg://…` connection string the API/worker/beat use at runtime | Built from the real host, port, database name, and the password above — never reuse the `gridkeep:gridkeep` value `docker-compose.yml` ships for local dev |
| `DATABASE_MIGRATION_URL` | The same database, `postgresql+psycopg://…` scheme, used only for `alembic upgrade head` | Same credentials as `DATABASE_URL`, different driver prefix |
| `CORS_ALLOW_ORIGINS` | JSON array of the real frontend origin(s), e.g. `["https://app.example.com"]` | Must exactly match where the browser reaches `web` — a mismatch here breaks every authenticated request, not just CORS preflight |
| `APP_BASE_URL` | The real frontend origin, used to build the clickable links in verification/reset/invitation emails | Same value as the single origin in `CORS_ALLOW_ORIGINS` in the common case of one frontend domain |
| `VAULT_LOCAL_MASTER_KEY` | Credential-vault master key (see the C-02 caveat above) | `openssl rand -base64 48` — **never** the value shipped in `docker-compose.yml`; the API refuses to boot if it detects that exact default |
| `NEXT_PUBLIC_API_BASE_URL` | The real API origin, baked into the frontend's JS bundle at build time (`web.Dockerfile`) | Must be reachable from the end user's browser — this is not a server-to-server URL |

Generate secrets with a real CSPRNG (`openssl rand`, your cloud provider's Secrets Manager/KMS, or a
password manager's generator) — never hand-type a password, and never reuse a value from
`docker-compose.yml`, which is intentionally public and insecure by design for local development.

## First boot sequence

```bash
# 1. Set every variable above in your shell or a real secrets-injection
#    mechanism (do not commit them to a .env file that gets checked in).

# 2. Validate the merged configuration before starting anything:
docker compose -f docker-compose.yml -f docker-compose.production.yml config

# 3. If step 2 succeeds cleanly (no "required variable ... is missing"
#    errors), start the stack:
docker compose -f docker-compose.yml -f docker-compose.production.yml up -d

# 4. Confirm the api container actually started, not crash-looped on the
#    Settings fail-closed check:
docker compose -f docker-compose.yml -f docker-compose.production.yml logs api --tail=50
```

If the `api` container exits immediately with a `ValidationError` naming specific development defaults
still in effect, that is the fail-closed check working as designed (Milestone 29) — fix the named
variable(s) and retry. This is deliberately not a warning; it is a hard stop.

## After first boot

- Put a reverse proxy in front of `api` (port 8000) and `web` (port 3000) with a real TLS certificate.
  Until you do, the application is not safe to expose to real users despite every other control in this
  milestone — `Secure` cookies are simply never sent by the browser back to a plain-HTTP origin, which
  will look like broken login, not like a security warning.
- Track every open item in `docs/security-findings-register.md` against your own go-live checklist — this
  runbook closes the configuration-hygiene gap (finding H-02); it does not close C-01 or C-02, both of
  which remain open until their dedicated milestones ship.
