#!/usr/bin/env bash
# Run the REAL docker-compose.prod.yml on a build VM and verify it with real Chromium. Records what this was and was not.
#
#   infrastructure/verify/prod-compose.sh up        # build + start (needs .env.production; see .env.production.example)
#   infrastructure/verify/prod-compose.sh down
#
# Deviations it makes (and that the verification record must state):
#  - MINIO_BLOCKED=1 disables minio/minio-init when quay.io cannot be reached (403 in the sandbox this was written in).
#  - TLS_PROXY_CA=/path/ca.pem adds a TLS-intercepting proxy's CA to the BUILDER stage of copies of the Dockerfiles (runtime stages untouched).
# On the real host neither is needed: unset both and run the compose file unmodified.
set -euo pipefail
cd "$(dirname "$0")/../.."
ENVF="${ENV_FILE:-.env.production}"
WORK="${WORK:-/tmp/woi-prod-verify}"; mkdir -p "$WORK"
FILES=(-f docker-compose.prod.yml)
{
  echo "services:"
  if [ "${MINIO_BLOCKED:-0}" = 1 ]; then
    echo '  minio: {profiles: ["blocked"]}'; echo '  minio-init: {profiles: ["blocked"]}'
  fi
  # one mapping per service (YAML forbids repeating a key)
  API_BUILD=""; [ -n "${TLS_PROXY_CA:-}" ] && API_BUILD='build: {dockerfile: .verify-build/api.Dockerfile}'
  API_DEPS=""; [ "${MINIO_BLOCKED:-0}" = 1 ] && API_DEPS='depends_on: !override {migrate: {condition: service_completed_successfully}, redis: {condition: service_healthy}}'
  [ -n "$API_BUILD$API_DEPS" ] && echo "  api: {${API_BUILD}${API_BUILD:+${API_DEPS:+, }}${API_DEPS}}"
  if [ -n "${TLS_PROXY_CA:-}" ]; then
    mkdir -p .verify-build; cp "$TLS_PROXY_CA" .verify-ca.crt
    for n in api worker web; do
      awk 'NR==1{print; print "COPY .verify-ca.crt /tmp/proxy-ca.crt"; print "ENV NODE_EXTRA_CA_CERTS=/tmp/proxy-ca.crt SSL_CERT_FILE=/tmp/proxy-ca.crt REQUESTS_CA_BUNDLE=/tmp/proxy-ca.crt PIP_CERT=/tmp/proxy-ca.crt UV_NATIVE_TLS=1"; next} {print}' "apps/$n/Dockerfile" > ".verify-build/$n.Dockerfile"
    done
    echo "  migrate: {build: {dockerfile: .verify-build/api.Dockerfile}}"
    echo "  worker: {build: {dockerfile: .verify-build/worker.Dockerfile}}"; echo "  web: {build: {dockerfile: .verify-build/web.Dockerfile}}"
  fi
} > "$WORK/override.yml"
[ "$(wc -l < "$WORK/override.yml")" -gt 1 ] && FILES+=(-f "$WORK/override.yml")
DC=(docker compose --env-file "$ENVF" "${FILES[@]}")
case "${1:-up}" in
  up)   "${DC[@]}" build && "${DC[@]}" up -d && "${DC[@]}" ps ;;
  down) "${DC[@]}" down -v; rm -rf .verify-build .verify-ca.crt ;;
  *) echo "usage: $0 up|down"; exit 2 ;;
esac
