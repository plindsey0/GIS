from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from gis.database_safety import ephemeral_migration_database, explicit_alembic_config

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL is required. Tests fail closed and never fall back to DATABASE_URL."
    )


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    config = explicit_alembic_config(TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session")
def migration_database_url() -> Iterator[str]:
    with ephemeral_migration_database(TEST_DATABASE_URL) as (url, identity):
        print(
            "MIGRATION TEST DATABASE: "
            f"environment={identity.environment} host={identity.host} port={identity.port} "
            f"database={identity.database} disposable={identity.disposable} "
            f"test_run_id={identity.test_run_id}"
        )
        command.upgrade(explicit_alembic_config(url), "head")
        yield url


@pytest.fixture()
def session(migrated_database: None) -> Iterator[Session]:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, expire_on_commit=False) as db_session:
            yield db_session
            db_session.close()
        if transaction.is_active:
            transaction.rollback()
    engine.dispose()
