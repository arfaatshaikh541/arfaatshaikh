#!/usr/bin/env bash
# Run database migrations against DATABASE_URL. Used locally, in CI, and as
# the first step of the api container's startup command in docker-compose.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../apps/api"
alembic upgrade head
