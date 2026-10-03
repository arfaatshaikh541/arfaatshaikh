# Operations: worker, email, backups, restore

## Background worker (`worker` service)

One Celery process group runs the tasks **and** the schedule (`--beat`). Do not scale this service past one replica or the schedule would run twice (the tasks are idempotent, so a duplicate is harmless but wasteful).

| Task | Schedule | What it does | Failure behaviour |
|---|---|---|---|
| `woi.email.send_outbox` | every 60 s | Sends verification and password-reset mail queued in `email_outbox` over SMTP, then removes the token from the stored row. Mail older than its token's lifetime is marked failed ("expired before delivery") and never sent. | Mail server down: the message stays queued and the task retries (5 times, 30 s to 15 min backoff). Mail refused: that message is marked failed once. **If `WOI_SMTP_HOST` is empty nothing is sent and each run logs a warning with the number waiting.** |
| `woi.auth.purge_expired` | daily 03:17 UTC | Deletes sessions, verification/reset tokens and sent mail that expired or finished more than 30 days ago. | Retries 3 times on a database error. |
| `woi.data.validate` | daily 03:41 UTC | Runs the 14 data-governance checks and writes one `system.data_validation` row to the platform audit log. Takes about 150 s on the full database. | A failed check is a finding, not a fault: it is logged at ERROR and recorded; there is no automatic retry. |

Check them: `docker compose exec worker celery -A worker.celery_app:celery_app inspect registered`. Run one now: `docker compose exec worker celery -A worker.celery_app:celery_app call woi.data.validate`.

There is deliberately **no scheduled import**: an unattended import would put unreviewed data in front of users. Imports run from the admin screen or `scripts/run_importer.py`, and stay unpublished until someone publishes them.

### Email (required for sign-up and password reset)

Set these in `.env.production` (see `.env.production.example`): `WOI_SMTP_HOST`, `WOI_SMTP_PORT` (587), `WOI_SMTP_USERNAME`, `WOI_SMTP_PASSWORD`, `WOI_SMTP_FROM`, `WOI_SMTP_STARTTLS`, and `WOI_PUBLIC_BASE_URL` (the link base, e.g. `https://app.arfaat.com/worldofislam`). Links carry the token in the URL fragment so it does not appear in server logs. Without `WOI_SMTP_HOST`, nobody receives a verification or reset email.

## Backups

The `backup` service writes `./backups/woi-<UTC timestamp>.sql.gz` (plain SQL, gzip) at start and every 24 h and deletes files older than `BACKUP_KEEP_DAYS` (14). **Copy that folder off the machine**; nothing uploads it to object storage. Each backup should be accompanied by `sha256sum` output; `infrastructure/verify/backup-restore.sh` shows the full cycle.

## Restore

1. Stop `api`, `worker`, `web` and `nginx`.
2. `./infrastructure/scripts/restore.sh backups/<file>.sql.gz` and type `RESTORE`. It drops and recreates the `public` schema, loads the dump as the superuser, and gives every object back to the application role (so row-level security applies again).
3. Start the services again; `migrate` is a no-op when the dump is at the current revision.
4. Verify: row counts, `docker compose run --rm api python scripts/validate_data.py`, and `/api/health/ready`.

**Choose the file by name.** The `backup` service writes a new file whenever it starts, so on a fresh stack the newest file can be a backup of an empty database.

## Verifying the whole stack

`infrastructure/verify/prod-compose.sh up` (with the two documented sandbox switches), then the two Chromium suites in `infrastructure/verify/`. Results of the last run, and every deviation, are in `data/verification-prod-compose.json`.
