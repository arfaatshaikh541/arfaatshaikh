# Production deployment (24/7 cloud server)

Everything needed for normal operation runs on the server. Your laptop is not involved; your
phone is needed only to complete a human-verification checkpoint.
Architecture and behaviour: `CLOUD_RUNTIME.md`. Security posture: `SECURITY_REVIEW.md`.

## 1. Server sizing (measured)

Measured with `docker stats` on the running stack in the build environment:

| State | postgres | web | scheduler | worker | total |
|---|---|---|---|---|---|
| Idle | 46 MiB | 74 MiB | 57 MiB | 60 MiB | ≈ 240 MiB |
| Worker with Chromium + one form context (local test page) | 46 MiB | 75 MiB | 57 MiB | 153 MiB | ≈ 330 MiB |

Image size: ≈ 4.0 GB uncompressed (the official Playwright image with Chromium and its OS dependencies).
Real employer pages are heavier than the local test page, and Chromium routinely uses several hundred
MiB for them; that was **not measurable here** because the build environment could not reach job sites.

Recommendation, derived from the measurements plus headroom for real pages: **2 vCPU, 2 GB RAM minimum;
4 GB recommended**; add about 1 GB per extra worker. **20 GB disk** (image, database, encrypted evidence
screenshots). Any Linux VPS with Docker Engine 24+ and the Compose plugin will do.

## 2. Install

```bash
git clone <this repo> && cd <repo>/job-autopilot
cp .env.example .env && chmod 600 .env
#   POSTGRES_PASSWORD=$(openssl rand -hex 24)
#   JOBAP_DOMAIN=autopilot.example.com          (DNS A record -> this server)
#   JOBAP_PUBLIC_BASE_URL=https://autopilot.example.com
docker compose build
mkdir -p secrets
docker run --rm job-autopilot:latest gen-master-key > secrets/master.key
sudo chown 1001:1001 secrets/master.key && sudo chmod 600 secrets/master.key   # containers run as uid 1001
docker compose --profile tls up -d          # includes Caddy (automatic HTTPS). Omit the profile if you have a proxy.
docker compose exec web autopilot create-admin --email you@example.com
docker compose ps                           # all services "healthy"
```

**Back up `secrets/master.key` offline.** It is never stored in the database or in backups; without it,
stored credentials, CVs, sessions and evidence cannot be decrypted.

## 3. What keeps it running

* `restart: unless-stopped` on every service; `init: true` for signal handling.
* HEALTHCHECKs: web `/healthz`, scheduler and worker a heartbeat file that is touched only after a
  successful DB heartbeat.
* Self-watchdogs: a worker or scheduler whose main loop stalls exits, and Docker restarts it.
* The scheduler watchdog marks workers with no heartbeat for 120 s as DEAD and reclaims their tasks safely.
* DB connections have connect and TCP keepalive timeouts, so partitions cannot hang a process for long.
* Graceful stop: `stop_grace_period` of 2 min (worker) / 30 s (scheduler).

## 4. Security hardening in the compose file

* web/scheduler/worker: non-root (uid 1001), `cap_drop: ALL`, `no-new-privileges`, read-only root fs, tmpfs `/tmp`.
* Published ports: `127.0.0.1:8000` (web) and 80/443 (Caddy profile). PostgreSQL and the worker session
  port 9310 are internal only. Chromium has no remote-debugging port.
* `JOBAP_ENVIRONMENT=production`: only https destinations on public hosts (SSRF-safe).

## 5. Logs and monitoring

* JSON logs on stdout, rotated by Docker (`json-file`, 20 MB × 5 per container):
  `docker compose logs -f worker`. Secrets are redacted by a mandatory filter.
* `GET /healthz` (no auth) for uptime monitors; `GET /health` (auth) for the full status JSON.
* `GET /metrics` in Prometheus text format: queue depth, tasks by type/status, applications by
  mode/status, heartbeat ages, verification requests, notification deliveries, and 24 h system events
  (browser restarts, dead workers, verification requested/completed/timeout). Put a token in a file and
  set `JOBAP_METRICS_TOKEN_FILE`, or scrape with a logged-in session.
* The dashboard Overview is the live operations view (system, scheduler, workers with activity,
  browser sessions, queue, open verifications).

## 6. Backups

```bash
scripts/backup.sh            # -> backups/<UTC timestamp>/{db.dump, appdata.tgz, docker-compose.yml, env.nonsecret, SHA256SUMS}
```
Contents: the PostgreSQL custom-format dump (credentials inside are vault ciphertext), the data volume
(CVs and evidence, already encrypted) and non-secret config. Excluded: the master key and the DB
password. Schedule it with cron (e.g. `15 3 * * * cd /srv/job-autopilot && scripts/backup.sh`) and copy
`backups/` off the server.

## 7. Restore (new server)

1. Install Docker, clone the repo, create `.env` (new `POSTGRES_PASSWORD` is fine).
2. Restore `secrets/master.key` from your offline copy (`chown 1001:1001`, `chmod 600`).
3. `docker compose build`, then `scripts/restore.sh backups/<timestamp>`: checksums are verified,
   the DB and data volume are restored, and services start.
4. Reconciliation of in-progress work is automatic: tasks whose worker no longer exists are reclaimed.
   Pre-submit applications are re-queued; applications that were `SUBMITTING` or held for verification
   become `UNKNOWN` / `VERIFICATION_TIMEOUT` and are never retried blindly. Review them on the
   Applications page (and let IMAP reconciliation look for confirmation emails).

## 8. Updates

```bash
git pull && docker compose build && docker compose --profile tls up -d
```
Schema changes are applied at startup by the idempotent migration runner (`autopilot/migrations.py`,
table `schema_migrations`). Take a backup first.

## 9. Laptop-independence acceptance test (run on your server)

1. `docker compose ps`: all healthy. Dashboard → Overview: system ONLINE, scheduler RUNNING,
   workers N/N HEALTHY.
2. Add a job source, set Automation → START, and note the "Last successful discovery" time.
3. Close your laptop, or turn it off, for at least two search intervals.
4. From your phone (mobile data, not your home network): open the dashboard and check that discovery
   ran again, the task list advanced, heartbeats are current, and reports keep being generated at the
   configured Dubai time.
5. For the verification path: when a challenge occurs you receive the notification, open the link on
   your phone, complete the challenge, and see the application resume.

## What was verified in the build environment

The full stack (`postgres` from the official image mirror, web, scheduler, worker) was brought up with
this compose file, hardened as above, in `production` mode. Measured and drilled:

* all services healthy; published ports and privileges verified from outside the containers
* cold start without restarts (after fixing a registry race found on the first cold start)
* worker SIGKILL → automatic restart; network partition → DEAD detection → recovery after
  reconnect (after fixing unbounded DB socket hangs found by this drill); PostgreSQL restart → no
  process restarts; Docker daemon restart → all services back, state intact
* unattended operation: scheduled discovery attempted against the real Greenhouse API (blocked by
  the build environment's egress policy and recorded as an error, 0 jobs), per-host backoff, and the
  daily report generated
