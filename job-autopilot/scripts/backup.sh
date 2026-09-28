#!/usr/bin/env bash
# Backup: PostgreSQL (custom-format dump) + the app data volume (CV files and evidence, already
# AES-256-GCM encrypted) + non-secret deployment config. The master key is NOT included; back it up
# separately (offline). Credentials inside the dump are vault ciphertext only.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-backups}/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT"
docker compose exec -T postgres pg_dump -U autopilot -d autopilot -Fc > "$OUT/db.dump"
VOL="$(docker volume ls -q | grep -E '(^|_)appdata$' | head -1)"
docker run --rm -v "$VOL":/data:ro -v "$PWD/$OUT":/b public.ecr.aws/docker/library/alpine:3 \
  tar czf /b/appdata.tgz -C /data .
cp docker-compose.yml "$OUT/"; [ -f deploy/Caddyfile ] && cp deploy/Caddyfile "$OUT/"
grep -vE '^POSTGRES_PASSWORD=' .env > "$OUT/env.nonsecret" || true   # the DB password is not copied
( cd "$OUT" && sha256sum db.dump appdata.tgz > SHA256SUMS )
echo "backup written to $OUT (master key NOT included)"
