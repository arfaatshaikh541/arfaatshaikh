#!/bin/sh
# Restore a dump produced by backup-loop.sh into the running postgres service.
#   ./infrastructure/scripts/restore.sh backups/woi-20261001T020000Z.sql.gz
# This REPLACES the contents of the database (the public schema is dropped and recreated). Stop the api/worker first.
# The restore runs as the superuser (foreign-key checks must see every row), then ownership of every object is given
# back to the application role so row-level security applies to the application again.
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <dump.sql.gz>" >&2; exit 2; }
printf 'This will overwrite the production database. Type RESTORE to continue: '
read -r answer
[ "$answer" = "RESTORE" ] || { echo "aborted"; exit 1; }
APP_ROLE="$(grep '^WOI_APP_DB_USER=' .env.production | cut -d= -f2)"
COMPOSE="docker compose --env-file .env.production -f docker-compose.prod.yml"
PSQL='psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
{ echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"; gunzip -c "$1"; } | $COMPOSE exec -T postgres sh -c "$PSQL"
$COMPOSE exec -T postgres sh -c "$PSQL -v app='\"$APP_ROLE\"'" < infrastructure/postgres/assign-ownership.sql
echo "restore complete; start the api and worker again"
