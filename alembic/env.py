from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Core Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Setup logging configuration if the file exists
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Track database schema metadata for tracking migrations
from app.database import Base
from app.models.entities import *  # Imports our table entities

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    # Handles migrations without an active database connection
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
    # Handles live migrations against the active target database connection
    from app.core.config import settings
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
