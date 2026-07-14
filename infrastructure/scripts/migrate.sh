#!/usr/bin/env bash
# Runs Alembic migrations against the migrator role, inside the api container.
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose -f infrastructure/docker/docker-compose.yml exec -T api \
  bash -c "cd /app/apps/api && alembic upgrade head"
