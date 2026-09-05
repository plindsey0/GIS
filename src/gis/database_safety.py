"""Fail-closed database identity controls for destructive migration tests."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

LOGGER = logging.getLogger(__name__)
DISPOSABLE_PREFIX = "gis_migration_test_"
DENIED_DATABASES = {"gis", "postgres", "template0", "template1"}
REFUSAL = "REFUSING DESTRUCTIVE MIGRATION TEST AGAINST NON-DISPOSABLE DATABASE"


class DestructiveDatabaseSafetyError(RuntimeError):
    """Raised before destructive SQL when database identity is not disposable."""


@dataclass(frozen=True)
class DatabaseIdentity:
    environment: str
    host: str
    port: int | None
    database: str
    disposable: bool
    test_run_id: str


def safe_identity(url: str, environment: str, test_run_id: str) -> DatabaseIdentity:
    parsed = make_url(url)
    return DatabaseIdentity(
        environment=environment,
        host=parsed.host or "local-socket",
        port=parsed.port,
        database=parsed.database or "",
        disposable=(parsed.database or "").startswith(DISPOSABLE_PREFIX),
        test_run_id=test_run_id,
    )


def assert_disposable_database_for_destructive_test(
    url: str | None,
    *,
    environment: str,
    test_run_id: str,
    authorization_token: str,
    development_url: str | None = None,
) -> DatabaseIdentity:
    """Require positive ephemeral ownership and secondary persistent-DB denial."""

    if not url:
        raise DestructiveDatabaseSafetyError(f"{REFUSAL}: explicit test database URL is required")
    identity = safe_identity(url, environment, test_run_id)
    LOGGER.warning("destructive_migration_database_identity %s", asdict(identity))
    expected_name = f"{DISPOSABLE_PREFIX}{test_run_id}"
    expected_token = f"gis-destructive-test:{test_run_id}"
    development_database = make_url(development_url).database if development_url else None
    reasons = []
    if environment != "test":
        reasons.append("environment is not TEST")
    if identity.database in DENIED_DATABASES or identity.database == development_database:
        reasons.append("database is persistent or denied")
    if identity.database != expected_name:
        reasons.append("database is not owned by this test run")
    if authorization_token != expected_token:
        reasons.append("internal destructive-test authorization is invalid")
    if reasons:
        raise DestructiveDatabaseSafetyError(
            f"{REFUSAL}: database={identity.database or '<missing>'}; " + "; ".join(reasons)
        )
    return identity


def explicit_alembic_config(url: str) -> Config:
    """Build Alembic config whose URL cannot be replaced by inherited app config."""

    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["explicit_database_url"] = url
    return config


def destructive_alembic_config(
    url: str | None,
    *,
    environment: str,
    test_run_id: str,
    authorization_token: str,
    development_url: str | None = None,
) -> Config:
    assert_disposable_database_for_destructive_test(
        url,
        environment=environment,
        test_run_id=test_run_id,
        authorization_token=authorization_token,
        development_url=development_url,
    )
    assert url is not None
    config = explicit_alembic_config(url)
    config.attributes["destructive_test_authorized"] = True
    return config


def _database_url(base: URL, database: str) -> str:
    return base.set(database=database).render_as_string(hide_password=False)


@contextmanager
def ephemeral_migration_database(base_url: str | None) -> Iterator[tuple[str, DatabaseIdentity]]:
    """Create, positively identify, yield, and remove one disposable PostgreSQL DB."""

    if not base_url:
        raise DestructiveDatabaseSafetyError(
            f"{REFUSAL}: TEST_DATABASE_URL is required; development fallback is forbidden"
        )
    base = make_url(base_url)
    development_url = os.environ.get("DATABASE_URL")
    if base.database in DENIED_DATABASES or (
        development_url and base.database == make_url(development_url).database
    ):
        raise DestructiveDatabaseSafetyError(
            f"{REFUSAL}: administrative test URL identifies persistent database={base.database}"
        )
    run_id = uuid.uuid4().hex[:16]
    database = f"{DISPOSABLE_PREFIX}{run_id}"
    token = f"gis-destructive-test:{run_id}"
    admin_url = _database_url(base, "postgres")
    test_url = _database_url(base, database)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database}"'))
            created = True
        identity = assert_disposable_database_for_destructive_test(
            test_url,
            environment="test",
            test_run_id=run_id,
            authorization_token=token,
            development_url=development_url,
        )
        yield test_url, identity
    finally:
        if created:
            with admin.connect() as connection:
                connection.execute(
                    text(
                        "select pg_terminate_backend(pid) from pg_stat_activity where datname=:db"
                    ),
                    {"db": database},
                )
                connection.execute(text(f'DROP DATABASE "{database}"'))
        admin.dispose()
