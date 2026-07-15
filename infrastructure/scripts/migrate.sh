#!/usr/bin/env bash
# Runs Alembic migrations against the configured DATABASE_MIGRATION_URL.
set -euo pipefail
cd "$(dirname "$0")/../../apps/api"
alembic upgrade head
