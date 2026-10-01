#!/bin/sh
# Restore a dump produced by backup-loop.sh into the running postgres service.
#   ./infrastructure/scripts/restore.sh backups/woi-20261001T020000Z.sql.gz
# This REPLACES the contents of the target database (the public schema is dropped and recreated). Stop the api/worker first.
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <dump.sql.gz>" >&2; exit 2; }
printf 'This will overwrite the production database. Type RESTORE to continue: '
read -r answer
[ "$answer" = "RESTORE" ] || { echo "aborted"; exit 1; }
# SET ROLE makes the restored objects belong to the application role (a non-superuser, so row-level security applies).
APP_ROLE="$(grep '^WOI_APP_DB_USER=' .env.production | cut -d= -f2)"
{ echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public AUTHORIZATION \"$APP_ROLE\"; SET ROLE \"$APP_ROLE\";"; gunzip -c "$1"; } | docker compose --env-file .env.production -f docker-compose.prod.yml exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
