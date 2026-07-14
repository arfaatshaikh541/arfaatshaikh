from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.core.config import get_settings
from app.db.base import Base
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.entitlements import models as entitlements_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.permissions import models as permissions_models  # noqa: F401
from app.modules.subscriptions import models as subscriptions_models  # noqa: F401

# Import every module's models so Base.metadata is fully populated before
# autogenerate compares it against the database.
from app.modules.tenancy import models as tenancy_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
# Migrations always run as the app_migrator role (BYPASSRLS), never the
# runtime role, regardless of what DATABASE_URL is set to.
config.set_main_option("sqlalchemy.url", settings.migration_database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import engine_from_config

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
