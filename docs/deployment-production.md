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
- **A running HashiCorp Vault server.** Milestone 32 (finding C-02) adds a real production credential-vault
  adapter (`HashiCorpVaultAdapter`, backed by Vault's Transit secrets engine), but this repository does not
  run Vault itself — `VAULT_HASHICORP_ADDR` below must point at wherever Vault actually runs (a managed
  cluster, a separately-operated self-hosted instance), the same way this deployment already treats TLS
  termination as external infrastructure it configures a connection to rather than provisions. See
  "Provisioning HashiCorp Vault" below for the one-time setup that server needs before first boot.

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
| `VAULT_LOCAL_MASTER_KEY` | Master key for the *local* envelope-encryption adapter — validated even though production uses the Vault adapter below, so a later fallback to `VAULT_ADAPTER=local` never silently un-masks a stale shipped key | `openssl rand -base64 48` — **never** the value shipped in `docker-compose.yml`; the API refuses to boot if it detects that exact default |
| `VAULT_ADAPTER` | Which credential-vault adapter the application constructs | Must be the literal string `vault` — `local` (the default) is refused at boot in production |
| `VAULT_HASHICORP_ADDR` | The real Vault server's address | e.g. `https://vault.internal.example.com:8200` — see "Provisioning HashiCorp Vault" below |
| `VAULT_HASHICORP_TOKEN` | A Vault token scoped to this application's transit-key policy | Issued by Vault (AppRole or a periodic token, per your Vault deployment's own auth method) — never Vault's root token |
| `NEXT_PUBLIC_API_BASE_URL` | The real API origin, baked into the frontend's JS bundle at build time (`web.Dockerfile`) | Must be reachable from the end user's browser — this is not a server-to-server URL |

Generate secrets with a real CSPRNG (`openssl rand`, your cloud provider's Secrets Manager/KMS, or a
password manager's generator) — never hand-type a password, and never reuse a value from
`docker-compose.yml`, which is intentionally public and insecure by design for local development.

## Provisioning HashiCorp Vault

This repository's containers connect to Vault; they do not run it. Before first boot, against your own
Vault server (with a token that has Vault admin capability — this is a one-time infrastructure setup step,
not something `VAULT_HASHICORP_TOKEN` itself needs):

```bash
# 1. Enable the Transit secrets engine — the API/worker/beat token below is
#    never granted this capability (mounting engines is an infra-admin
#    operation, not an application one).
vault secrets enable transit

# 2. Create a policy scoped to exactly what the application needs: using
#    (and, on first boot, self-provisioning) its own named key — nothing
#    broader. `gridkeep-credential-vault` is the default
#    VAULT_HASHICORP_TRANSIT_KEY_NAME; change both if you set that
#    variable to something else.
cat <<'POLICY' | vault policy write gridkeep-credential-vault -
path "transit/keys/gridkeep-credential-vault" {
  capabilities = ["create", "read"]
}
path "transit/encrypt/gridkeep-credential-vault" {
  capabilities = ["update"]
}
path "transit/decrypt/gridkeep-credential-vault" {
  capabilities = ["update"]
}
POLICY

# 3. Issue a token (or, for a real deployment, configure AppRole/Kubernetes
#    auth against this same policy — a long-lived static token is the
#    simplest starting point, not the recommended end state):
vault token create -policy=gridkeep-credential-vault -period=768h
```

The application self-provisions the named Transit key itself on first use (idempotent — the same
create-or-converge pattern migration `34016597f04f` uses for the `gridkeep_app` Postgres role), so you do
not need to create the key by hand — only the engine mount and policy above, which the application's own
least-privilege token cannot do itself. `exportable=false` (Vault's default, which this key is created
with) means nobody — not even a Vault admin — can extract the raw key material through the API; only
encrypt/decrypt operations against it are ever possible.

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
  runbook closes the configuration-hygiene gap (finding H-02) and, as of Milestone 32, the credential-vault
  gap (finding C-02). Finding C-02's own scope is the *adapter* — this runbook does not cover Vault's own
  operational hardening (TLS between the application and Vault, Vault's own HA/unseal/backup posture,
  auth-method choice beyond the starter static token above), which remains the operator's responsibility
  the same way Postgres's own backup strategy does.
