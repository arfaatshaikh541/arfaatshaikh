#!/usr/bin/env bash
# Sets up a locally-running PostgreSQL instance with the migrator/app role
# split GRIDKEEP relies on for defense-in-depth RLS (see docs/architecture
# and apps/api/app/core/db.py). Use this for running the API directly
# against a local `postgres` service instead of the Dockerized stack.
#
# Requires: a running local PostgreSQL server reachable as the `postgres`
# superuser (adjust PSQL_CMD below if your setup differs).
set -euo pipefail

PSQL_CMD=${PSQL_CMD:-"sudo -u postgres psql"}

MIGRATOR_PASSWORD=${MIGRATOR_PASSWORD:-gridkeep_migrator_dev_password}
APP_PASSWORD=${APP_PASSWORD:-gridkeep_app_dev_password}

echo "Creating roles and databases (idempotent)..."

$PSQL_CMD <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gridkeep_migrator') THEN
    CREATE ROLE gridkeep_migrator WITH LOGIN PASSWORD '${MIGRATOR_PASSWORD}' BYPASSRLS CREATEDB;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gridkeep_app') THEN
    CREATE ROLE gridkeep_app WITH LOGIN PASSWORD '${APP_PASSWORD}' NOBYPASSRLS;
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE gridkeep OWNER gridkeep_migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gridkeep')\gexec

SELECT 'CREATE DATABASE gridkeep_test OWNER gridkeep_migrator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gridkeep_test')\gexec
SQL

for DB in gridkeep gridkeep_test; do
  $PSQL_CMD -d "$DB" <<SQL
GRANT ALL ON SCHEMA public TO gridkeep_migrator;
GRANT USAGE ON SCHEMA public TO gridkeep_app;
ALTER DEFAULT PRIVILEGES FOR ROLE gridkeep_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gridkeep_app;
ALTER DEFAULT PRIVILEGES FOR ROLE gridkeep_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO gridkeep_app;
SQL
done

echo "Done. Databases 'gridkeep' and 'gridkeep_test' are ready."
echo "Next: cd apps/api && cp .env.example .env && uv sync && uv run alembic upgrade head"
