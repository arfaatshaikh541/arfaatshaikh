#!/usr/bin/env bash
# Restore a backup made by backup.sh onto a fresh server that already has: this repo, .env with
# POSTGRES_PASSWORD, and secrets/master.key restored from your offline copy.
#   scripts/restore.sh backups/20260928T200000Z
set -euo pipefail
cd "$(dirname "$0")/.."
B="$1"
( cd "$B" && sha256sum -c SHA256SUMS )
[ -s secrets/master.key ] || { echo "restore secrets/master.key first"; exit 1; }
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U autopilot -d autopilot >/dev/null 2>&1; do sleep 2; done
docker compose stop web scheduler worker 2>/dev/null || true
docker compose exec -T postgres pg_restore -U autopilot -d autopilot --clean --if-exists < "$B/db.dump"
docker compose create worker >/dev/null 2>&1 || true
VOL="$(docker volume ls -q | grep -E '(^|_)appdata$' | head -1)"
docker run --rm -v "$VOL":/data -v "$PWD/$B":/b:ro public.ecr.aws/docker/library/alpine:3 \
  sh -c 'rm -rf /data/* && tar xzf /b/appdata.tgz -C /data && chown -R 1001:1001 /data'
docker compose up -d
echo "restored. In-flight applications are reconciled automatically: SUBMITTING/verification holds whose worker"
echo "is gone become UNKNOWN / VERIFICATION_TIMEOUT (never retried blindly). Review them on the Applications page."
