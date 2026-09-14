# Local development

Docker is **optional**. Everything below was verified in a sandbox with no
Docker daemon available at all (`docker info` fails to reach
`/var/run/docker.sock`) — the native path is the one actually exercised in
this repository's own verification pass (`docs/FINAL_AUDIT.md` §9).

## Requirements (native path)

- PostgreSQL 16+ and Redis, running locally or reachable over the network
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- Node.js 20.9+ and pnpm 10.15.1 (via Corepack: `corepack enable`)
- MinIO (or another S3-compatible store) only if you need file storage
  features; the app and its tests run without it (`/health/ready` will
  correctly report `object_storage: false` until one is configured)

## Procedure

1. Create a database and user, e.g.:
   ```bash
   sudo -u postgres createuser world_of_islam --pwprompt
   sudo -u postgres createdb world_of_islam --owner=world_of_islam
   ```
2. Copy `.env.example` to `apps/api/.env` and fill in real values —
   `WOI_DATABASE_URL` pointing at the database above,
   `WOI_REDIS_URL`/`WOI_CELERY_*` at a local Redis, and a `WOI_SECRET_KEY`
   of at least 32 characters. Leave `WOI_BASE_PATH` and
   `NEXT_PUBLIC_WOI_API_ORIGIN` unset for local dev — see
   `docs/deployment/base-path.md` for production values.
3. Install and migrate the API:
   ```bash
   cd apps/api
   uv sync
   uv run alembic -c alembic.ini upgrade head
   uv run pytest -q            # 544 tests as of this pass
   uv run uvicorn app.main:app --reload --port 8000
   ```
4. In another shell, install and run the web app:
   ```bash
   corepack enable
   pnpm install
   pnpm --filter @world-of-islam/web dev
   ```
5. Check `http://localhost:8000/health/live`, then
   `http://localhost:8000/health/ready`, then
   `http://localhost:3000` (redirects to `/en`).
6. `pnpm --filter @world-of-islam/web typecheck`, `lint`, `test`, and
   `build` all run without Docker or a database.

Root-level convenience scripts also work: `pnpm dev:web`, `pnpm build:web`,
`pnpm lint:web`, `pnpm typecheck:web`, `pnpm test:web` (see `package.json`).
For the worker: `cd apps/worker && uv run celery -A worker.celery_app worker
--loglevel=info` (requires the same Redis/broker configuration as the API;
the worker's own code was not exercised in the verification pass).

## Docker path (optional, unchanged behavior otherwise)

1. Copy `.env.example` to `.env` at the repo root.
2. Replace all placeholder passwords and `WOI_SECRET_KEY`.
3. For Redis, ensure `WOI_REDIS_URL`, Celery URLs and `REDIS_PASSWORD` use
   the same password configuration.
4. Run `docker compose config` to validate interpolation (works without a
   daemon).
5. Run `docker compose up --build`. **Changing `WOI_BASE_PATH` or
   `NEXT_PUBLIC_WOI_API_ORIGIN` requires `--build`**, not just `up` — see
   `docs/deployment/base-path.md` §5.
6. Check `/health/live`, then `/health/ready`.
7. Run `make verify` for host-side checks (lint + tests, no Docker
   required for this step either).

**Note:** the Docker image builds themselves were not exercised in this
pass — no daemon was available in the verification environment. Run
`docker compose up --build` once yourself before relying on this path in
production; the Dockerfiles were fixed for a real bug (build-time
`NEXT_PUBLIC_*` args, see `docs/FINAL_AUDIT.md` §5) but that fix has only
been validated by inspection and by the equivalent native build, not by an
actual `docker build`.
