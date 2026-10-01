#!/bin/sh
# Bring up the production-like verification stack at https://woi.test/worldofislam (self-signed certificate).
#   infrastructure/verify/run.sh up [dump.pgcustom]     build-free start; optionally restores a pg_dump -Fc dump first
#   infrastructure/verify/run.sh down
# Point a browser at it with:  --host-resolver-rules="MAP woi.test 127.0.0.1"  and accept the self-signed certificate.
# Secrets are generated into $WORK (default /tmp/woi-verify) and never committed.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-/tmp/woi-verify}"
COMPOSE="docker compose --env-file $WORK/compose.env -f $HERE/docker-compose.verify.yml"
case "${1:-up}" in
down) $COMPOSE down -v; exit 0 ;;
up) ;;
*) echo "usage: $0 up [dump] | down" >&2; exit 2 ;;
esac
mkdir -p "$WORK/certs"
if [ ! -f "$WORK/certs/fullchain.pem" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 7 -subj "/CN=woi.test" -addext "subjectAltName=DNS:woi.test" \
    -keyout "$WORK/certs/privkey.pem" -out "$WORK/certs/fullchain.pem" 2>/dev/null
fi
if [ ! -f "$WORK/compose.env" ]; then
  gen() { openssl rand -hex "$1"; }
  PG_SU="$(gen 12)"; PG_APP="$(gen 12)"; RD="$(gen 12)"
  cat > "$WORK/compose.env" <<ENV
WOI_ENV_FILE=$WORK/api.env
WOI_PUBLIC_HOST=woi.test
WOI_BASE_PATH=/worldofislam
WOI_CERT_DIR=$WORK/certs
POSTGRES_DB=world_of_islam
POSTGRES_USER=woi_admin
POSTGRES_PASSWORD=$PG_SU
WOI_APP_DB_USER=world_of_islam
WOI_APP_DB_PASSWORD=$PG_APP
REDIS_PASSWORD=$RD
ENV
  cat > "$WORK/api.env" <<ENV
WOI_ENVIRONMENT=production
WOI_LOG_LEVEL=INFO
WOI_ALLOWED_ORIGINS=https://woi.test
WOI_SECRET_KEY=$(gen 32)
WOI_COOKIE_SECURE=true
WOI_COOKIE_PATH=/worldofislam
WOI_ROOT_PATH=
WOI_AUTH_RATE_LIMIT=10
WOI_FORWARDED_ALLOW_IPS=172.31.200.10
WOI_DATABASE_URL=postgresql+asyncpg://world_of_islam:$PG_APP@postgres:5432/world_of_islam
WOI_REDIS_URL=redis://:$RD@redis:6379/0
WOI_CELERY_BROKER_URL=redis://:$RD@redis:6379/1
WOI_CELERY_RESULT_BACKEND=redis://:$RD@redis:6379/2
WOI_S3_ENDPOINT=http://minio-not-running:9000
WOI_S3_ACCESS_KEY=$(gen 8)
WOI_S3_SECRET_KEY=$(gen 16)
WOI_S3_BUCKET=world-of-islam
WOI_AI_MODE=local
WOI_EXTERNAL_AI_ENABLED=false
WOI_OLLAMA_BASE_URL=http://ollama-not-running:11434
WOI_OLLAMA_MODEL=llama3.1
WOI_OLLAMA_TIMEOUT_SECONDS=60
ENV
fi
$COMPOSE up -d postgres redis
until [ "$($COMPOSE ps postgres --format '{{.Health}}')" = "healthy" ]; do sleep 2; done
if [ -n "${2:-}" ]; then
  # Restore as the superuser (foreign keys must see every row), then give ownership back to the application role so row-level security applies.
  PGC="$($COMPOSE ps -q postgres)"
  . "$WORK/compose.env"
  docker exec "$PGC" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null
  docker cp "$2" "$PGC:/tmp/restore.dump"
  docker exec "$PGC" pg_restore --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" -j 4 /tmp/restore.dump || true
  docker exec -i "$PGC" psql -v ON_ERROR_STOP=1 -v app="\"$WOI_APP_DB_USER\"" -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$HERE/../postgres/assign-ownership.sql" >/dev/null
  docker exec "$PGC" rm -f /tmp/restore.dump
fi
$COMPOSE up -d
$COMPOSE ps
