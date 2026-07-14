#!/usr/bin/env bash
# Minimal TCP wait helper: infrastructure/scripts/wait-for-it.sh host:port -- command args
set -euo pipefail

hostport="$1"
shift
host="${hostport%%:*}"
port="${hostport##*:}"

if [[ "$1" == "--" ]]; then
  shift
fi

until (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1; do
  echo "Waiting for ${host}:${port}..."
  sleep 1
done

echo "${host}:${port} is available."

if [[ $# -gt 0 ]]; then
  exec "$@"
fi
