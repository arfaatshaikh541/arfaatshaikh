#!/usr/bin/env bash
# Waits for a TCP host:port to accept connections. Usage:
#   ./wait-for.sh postgres 5432 -- alembic upgrade head
set -euo pipefail

host="$1"
port="$2"
shift 2

if [ "${1:-}" = "--" ]; then
  shift
fi

echo "Waiting for ${host}:${port}..."
until (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; do
  sleep 1
done
echo "${host}:${port} is available."

if [ "$#" -gt 0 ]; then
  exec "$@"
fi
