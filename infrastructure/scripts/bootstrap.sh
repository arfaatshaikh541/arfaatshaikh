#!/usr/bin/env bash
# One-shot local environment bootstrap: install deps, start infra, migrate, seed.
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "==> Installing JS dependencies"
pnpm install

echo "==> Starting infrastructure (Postgres, Redis, object storage, mail capture)"
docker compose up -d postgres redis object-storage mail-capture

echo "==> Waiting for Postgres"
./infrastructure/scripts/wait-for.sh localhost 5432

echo "==> Installing API dependencies"
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

echo "==> Running migrations"
alembic upgrade head

echo "==> Seeding catalogue and demo data"
python -m seed.bootstrap
python -m seed.demo

echo ""
echo "Bootstrap complete. Start services with:"
echo "  docker compose up api worker beat web"
echo "or run each app individually — see README.md."
