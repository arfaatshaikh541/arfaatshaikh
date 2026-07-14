#!/usr/bin/env bash
# Provisions the two application-facing Postgres roles used in every
# environment (local dev and production alike), so the same migration
# and runtime code paths are exercised locally.
#
#   app_migrator  - used ONLY by Alembic. NOSUPERUSER, BYPASSRLS so schema
#                   changes are not blocked by row-level security policies.
#   app_runtime   - used by the API and worker at request time.
#                   NOSUPERUSER, NOBYPASSRLS so row-level security policies
#                   are always enforced for application traffic.
set -euo pipefail

: "${POSTGRES_MIGRATOR_USER:=app_migrator}"
: "${POSTGRES_MIGRATOR_PASSWORD:=app_migrator_dev_only}"
: "${POSTGRES_RUNTIME_USER:=app_runtime}"
: "${POSTGRES_RUNTIME_PASSWORD:=app_runtime_dev_only}"
: "${POSTGRES_DB:=cops}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_MIGRATOR_USER}') THEN
            CREATE ROLE ${POSTGRES_MIGRATOR_USER} WITH LOGIN PASSWORD '${POSTGRES_MIGRATOR_PASSWORD}' NOSUPERUSER BYPASSRLS CREATEDB;
        END IF;
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_RUNTIME_USER}') THEN
            CREATE ROLE ${POSTGRES_RUNTIME_USER} WITH LOGIN PASSWORD '${POSTGRES_RUNTIME_PASSWORD}' NOSUPERUSER NOBYPASSRLS;
        END IF;
    END
    \$\$;

    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_MIGRATOR_USER};
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${POSTGRES_RUNTIME_USER};

    ALTER DATABASE ${POSTGRES_DB} OWNER TO ${POSTGRES_MIGRATOR_USER};

    -- Ensure future tables/sequences created by the migrator are usable by
    -- the runtime role without per-migration GRANT statements.
    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_MIGRATOR_USER} IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${POSTGRES_RUNTIME_USER};
    ALTER DEFAULT PRIVILEGES FOR ROLE ${POSTGRES_MIGRATOR_USER} IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO ${POSTGRES_RUNTIME_USER};

    GRANT USAGE ON SCHEMA public TO ${POSTGRES_RUNTIME_USER};
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "citext";
EOSQL
