from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from gis.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

explicit_database_url = config.attributes.get("explicit_database_url")
database_url = explicit_database_url or os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata
DBT_MANAGED_SCHEMAS = {"gis_staging", "gis_intermediate", "gis_analytics"}


def include_name(
    name: str | None,
    type_: str,
    parent_names: dict[str, str | None],
) -> bool:
    """Keep dbt-owned relations outside Alembic's schema-drift boundary."""
    if type_ == "schema":
        return name not in DBT_MANAGED_SCHEMAS
    return parent_names.get("schema_name") not in DBT_MANAGED_SCHEMAS


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
