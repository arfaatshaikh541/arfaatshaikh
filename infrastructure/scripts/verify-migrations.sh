#!/bin/sh
# Proves the migration chain on an empty database: upgrade -> downgrade -> upgrade, with identical schemas.
# Needs a PostgreSQL server you may create databases on. Example:
#   WOI_PG_ADMIN_URL=postgresql://user:pass@localhost:5432/postgres ./infrastructure/scripts/verify-migrations.sh
set -eu
: "${WOI_PG_ADMIN_URL:?set WOI_PG_ADMIN_URL to an admin connection string (database postgres)}"
DB="woi_migration_check_$$"
BASE="${WOI_PG_ADMIN_URL%/*}"
psql "$WOI_PG_ADMIN_URL" -qc "create database $DB"
trap 'psql "$WOI_PG_ADMIN_URL" -qc "drop database if exists $DB"' EXIT
export WOI_DATABASE_URL="$(echo "$BASE/$DB" | sed 's#^postgresql://#postgresql+asyncpg://#')"
cd "$(dirname "$0")/../../apps/api"
count() { psql "$BASE/$DB" -Atc "select count(*) from information_schema.columns where table_schema='public'"; }
alembic -c alembic.ini upgrade head;   first=$(count)
alembic -c alembic.ini downgrade base; empty=$(psql "$BASE/$DB" -Atc "select count(*) from information_schema.tables where table_schema='public'")
alembic -c alembic.ini upgrade head;   second=$(count)
echo "columns after first upgrade: $first; tables after downgrade: $empty (alembic_version only = 1); columns after second upgrade: $second"
[ "$first" = "$second" ] && [ "$empty" = "1" ] && echo "MIGRATION CYCLE OK" || { echo "MIGRATION CYCLE FAILED"; exit 1; }
