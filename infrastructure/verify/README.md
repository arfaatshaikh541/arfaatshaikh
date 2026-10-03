# Production-like verification stack

`docker-compose.verify.yml` runs the production artifacts (API and web images built from `apps/api/Dockerfile` and
`apps/web/Dockerfile`, nginx with `infrastructure/nginx/woi.conf.template`, PostgreSQL 17, Redis) at
`https://woi.test/worldofislam` with a self-signed certificate. It omits MinIO, Ollama, the Celery worker and the backup job.

Why: the build environment cannot pull every image the real compose file needs (Docker Hub rate-limits it, `quay.io` is
blocked), so the real `docker-compose.prod.yml` could not be started there. What this stack proves is the base path, TLS
termination, proxy headers, the production configuration checks, migrations in the production image and the public and admin
pages; what it does not prove is MinIO-backed integrity storage, Ollama, the worker or backups.

If Docker Hub is rate-limited, build with the mirror: replace `FROM python:3.12-slim` and `FROM node:22-alpine` by
`mirror.gcr.io/library/...` in a temporary copy of each Dockerfile (the repository's Dockerfiles are not changed).

## Verifying the real production compose file

`prod-compose.sh` runs the unmodified `docker-compose.prod.yml` (with the two optional, disclosed deviations in its header), then
`browser-verify.cjs` (admin click-through, honesty and RTL/mobile checks) and `prod-extra-verify.cjs` (security headers, 404s, PWA,
authentication/authorisation, injection probes, rate limiting and the offline matrix) check it with real Chromium:

    NODE_PATH=$(npm root -g) BASE=https://app.arfaat.com/worldofislam ADMIN_EMAIL=... ADMIN_PASSWORD=... node infrastructure/verify/browser-verify.cjs
    NODE_PATH=$(npm root -g) BASE=https://app.arfaat.com/worldofislam ADMIN_EMAIL=... ADMIN_PASSWORD=... node infrastructure/verify/prod-extra-verify.cjs

The result of the last run, with every deviation, is in `data/verification-prod-compose.json`. That run was NOT on the real host and did not
include MinIO.
