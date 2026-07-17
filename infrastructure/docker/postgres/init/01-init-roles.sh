#!/usr/bin/env bash
# Runs once when the postgres container first initializes its data directory.
# Creates the two application-facing roles used throughout GRIDKEEP:
#   - MIGRATOR_DB_USER: BYPASSRLS, owns the schema, used only by Alembic.
#   - APP_DB_USER: NOBYPASSRLS, used by the API and worker at runtime.
# The bootstrap POSTGRES_USER (superuser) is never used by the application.
set -euo pipefail

: "${MIGRATOR_DB_USER:?MIGRATOR_DB_USER must be set}"
: "${MIGRATOR_DB_PASSWORD:?MIGRATOR_DB_PASSWORD must be set}"
: "${APP_DB_USER:?APP_DB_USER must be set}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE ${MIGRATOR_DB_USER} WITH LOGIN PASSWORD '${MIGRATOR_DB_PASSWORD}' BYPASSRLS CREATEDB;
    CREATE ROLE ${APP_DB_USER} WITH LOGIN PASSWORD '${APP_DB_PASSWORD}' NOBYPASSRLS;

    ALTER DATABASE ${POSTGRES_DB} OWNER TO ${MIGRATOR_DB_USER};

    GRANT ALL ON SCHEMA public TO ${MIGRATOR_DB_USER};
    GRANT USAGE ON SCHEMA public TO ${APP_DB_USER};

    -- Tables created hereafter by the migrator automatically grant the app
    -- role DML rights, so future migrations don't need manual grants.
    ALTER DEFAULT PRIVILEGES FOR ROLE ${MIGRATOR_DB_USER} IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_DB_USER};
    ALTER DEFAULT PRIVILEGES FOR ROLE ${MIGRATOR_DB_USER} IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${APP_DB_USER};
EOSQL
