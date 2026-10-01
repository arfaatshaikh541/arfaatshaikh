#!/bin/sh
# Runs once, when the PostgreSQL volume is first created (docker-entrypoint-initdb.d).
#
# The image's bootstrap user (POSTGRES_USER) is a superuser and superusers bypass row-level security. The application
# must not run as one, or the tenant-isolation policies in the schema would silently not apply. So the application
# gets its own non-superuser role that OWNS the database and runs the migrations; the superuser is used only by the
# backup job (pg_dump needs to read every row) and for administration.
set -eu
: "${WOI_APP_DB_USER:?}" "${WOI_APP_DB_PASSWORD:?}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE "$WOI_APP_DB_USER" LOGIN PASSWORD '$WOI_APP_DB_PASSWORD' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
ALTER DATABASE "$POSTGRES_DB" OWNER TO "$WOI_APP_DB_USER";
ALTER SCHEMA public OWNER TO "$WOI_APP_DB_USER";
SQL
