# Production deployment

The autonomous parts (scheduler and workers) run on a server, so nothing depends on your
laptop. You only need a browser or phone to administer it.

## 1. Server

* Any Linux VM with Docker Engine 24+ and the Compose plugin. Minimum 2 vCPU, 4 GB RAM,
  20 GB disk; add 1 GB RAM per extra worker (Chromium).
* A DNS name pointing at the server if you want HTTPS access from your phone (recommended).
* Outbound HTTPS to the ATS APIs/forms (`boards-api.greenhouse.io`, `job-boards.greenhouse.io`,
  `api.lever.co`, `jobs.lever.co`, `api.ashbyhq.com`, `jobs.ashbyhq.com`, and employer domains)
  and to your AI provider if you configure one.
* Set the server clock to NTP. Schedules use the timezone configured in the dashboard
  (default `Asia/Dubai`).

## 2. Install

```bash
git clone <this repo> && cd <repo>/job-autopilot
cp .env.example .env && chmod 600 .env
# edit .env: set POSTGRES_PASSWORD to a long random value, e.g. $(openssl rand -base64 32)

docker compose build
mkdir -p secrets
docker run --rm job-autopilot:latest gen-master-key > secrets/master.key
sudo chown 1001:1001 secrets/master.key && sudo chmod 600 secrets/master.key   # container runs as uid 1001
docker compose up -d
docker compose exec web autopilot create-admin --email you@example.com
docker compose ps        # web healthy; scheduler, worker, postgres running
```

**Back up `secrets/master.key` somewhere safe and offline.** Without it, stored credentials,
CV files, session cookies and evidence screenshots cannot be decrypted.

## 3. HTTPS (required for remote access)

The web container listens on `127.0.0.1:8000` only. Put a TLS reverse proxy in front.
Example with Caddy on the host (it obtains certificates automatically):

```
# /etc/caddy/Caddyfile
autopilot.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Keep `JOBAP_SECURE_COOKIES=true` (the default) so session cookies are `Secure`. You can also
restrict access to your own IPs or put the site behind a VPN / Tailscale.

## 4. Secret management

| Secret | Where it lives |
|---|---|
| Master encryption key | `secrets/master.key`, mounted as a Docker secret file (`JOBAP_MASTER_KEY_FILE`) |
| PostgreSQL password | `.env` (never committed; `.gitignore` excludes it) |
| Platform passwords, AI API keys | Entered in the dashboard, then AES-256-GCM encrypted in PostgreSQL |

If you have a cloud secret manager (AWS Secrets Manager, GCP Secret Manager, Vault, K8s
Secrets), have it write the master key to a file and point `JOBAP_MASTER_KEY_FILE` at it.
There is **no direct SDK integration** with those services. Mounting a file is the
supported interface.

### Key rotation
```bash
# 1. generate a new key; keep the old one
docker run --rm job-autopilot:latest gen-master-key > secrets/master.key.new
# 2. set JOBAP_OLD_MASTER_KEYS=<old key> in .env, swap the files, restart, then:
docker compose exec worker autopilot rotate-master-key
```
`rotate-master-key` re-encrypts credentials and platform sessions. CV files and evidence
screenshots keep their original key, so keep old keys in `JOBAP_OLD_MASTER_KEYS` for as long
as you need those files.

## 5. Scaling and limits

* `docker compose up -d --scale worker=2` adds browser workers. The scheduler dispatches **one
  application at a time** globally, and the application rate is bounded by your configured
  limits. Extra workers mainly help with discovery and evaluation.
* Only one scheduler is active at a time (PostgreSQL advisory lock). A second instance waits
  on standby.

## 6. Monitoring

* `GET /healthz` (no auth) returns `{"database": "HEALTHY"}`, or HTTP 503.
* `GET /health` (auth) and the Overview page show real status: scheduler heartbeat,
  live workers, browser, vault self-test, AI check, source errors, and last
  discovery/application/report times.
* Logs are JSON on stdout (`docker compose logs -f worker`) with timestamp, worker ID,
  platform, job ID, application ID, event, duration, result and error. Passwords, tokens and
  cookies are redacted by a mandatory log filter.

## 7. Backups

```bash
docker compose exec -T postgres pg_dump -U autopilot autopilot | gzip > backup-$(date +%F).sql.gz
docker run --rm -v job-autopilot_appdata:/data -v "$PWD":/b alpine tar czf /b/appdata-$(date +%F).tgz /data
```
Keep the master key backup separate from the data backups.

## 8. Updates

```bash
git pull && docker compose build && docker compose up -d
```
Workers finish their current task on SIGTERM (`stop_grace_period: 2m`). An application that
was mid-submission when a worker died is marked `UNKNOWN` and is never retried
automatically.

## 9. Schema changes

Tables are created idempotently at startup (`autopilot init-db`). No migration tool is
bundled yet. For future schema changes, add Alembic before altering existing tables, and
take a `pg_dump` first.

## What was verified in the build environment

* The image builds from `mcr.microsoft.com/playwright/python:v1.55.0-noble`. The web process
  serves `/healthz`. Chromium launches inside the container as the non-root user and reads a
  form. `docker compose config` validates.
* A full `docker compose up` was **not** run there, because Docker Hub (`postgres:16-alpine`)
  was rate-limited from that network. The processes were run against a local PostgreSQL 16
  instead.
