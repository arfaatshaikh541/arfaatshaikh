#!/usr/bin/env bash
# Seeds platform admin, demo tenant, plans, modules, and permission catalog.
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose -f infrastructure/docker/docker-compose.yml exec -T api \
  bash -c "cd /app/apps/api && python -m app.db.seed.run"
