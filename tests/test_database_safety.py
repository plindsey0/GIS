from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from gis.database_safety import (
    REFUSAL,
    DestructiveDatabaseSafetyError,
    assert_disposable_database_for_destructive_test,
    destructive_alembic_config,
    ephemeral_migration_database,
    explicit_alembic_config,
)


def authorize(url: str, run_id: str = "abc123") -> None:
    assert_disposable_database_for_destructive_test(
        url,
        environment="test",
        test_run_id=run_id,
        authorization_token=f"gis-destructive-test:{run_id}",
        development_url="postgresql+psycopg://gis:gis@localhost:5433/gis",
    )


@pytest.mark.parametrize("database", ["gis", "postgres", "template0", "template1"])
def test_persistent_database_names_are_refused(database: str) -> None:
    with pytest.raises(DestructiveDatabaseSafetyError, match=REFUSAL):
        authorize(f"postgresql+psycopg://gis:gis@localhost:5433/{database}")


def test_application_database_url_is_refused() -> None:
    with pytest.raises(DestructiveDatabaseSafetyError, match=REFUSAL):
        authorize("postgresql+psycopg://gis:gis@localhost:5433/gis")


def test_missing_test_database_url_fails_closed() -> None:
    with pytest.raises(DestructiveDatabaseSafetyError, match="explicit test database URL"):
        authorize(None)  # type: ignore[arg-type]


def test_test_environment_alone_is_insufficient() -> None:
    with pytest.raises(DestructiveDatabaseSafetyError, match=REFUSAL):
        authorize("postgresql+psycopg://gis:gis@localhost:5433/gis_test")


def test_disposable_name_requires_environment_and_internal_authorization() -> None:
    url = "postgresql+psycopg://gis:gis@localhost:5433/gis_migration_test_abc123"
    with pytest.raises(DestructiveDatabaseSafetyError, match="environment is not TEST"):
        assert_disposable_database_for_destructive_test(
            url,
            environment="development",
            test_run_id="abc123",
            authorization_token="gis-destructive-test:abc123",
        )
    with pytest.raises(DestructiveDatabaseSafetyError, match="authorization is invalid"):
        assert_disposable_database_for_destructive_test(
            url,
            environment="test",
            test_run_id="abc123",
            authorization_token="wrong",
        )


def test_correct_ephemeral_identity_is_allowed() -> None:
    authorize("postgresql+psycopg://gis:gis@localhost:5433/gis_migration_test_abc123")


def test_refusal_happens_before_destructive_callback() -> None:
    destructive_reached = False
    with pytest.raises(DestructiveDatabaseSafetyError, match=REFUSAL):
        destructive_alembic_config(
            os.environ.get("DATABASE_URL"),
            environment="test",
            test_run_id="missing",
            authorization_token="gis-destructive-test:missing",
            development_url=os.environ.get("DATABASE_URL"),
        )
        destructive_reached = True
    assert destructive_reached is False


def test_explicit_alembic_url_is_not_an_implicit_application_fallback() -> None:
    url = "postgresql+psycopg://gis:gis@localhost:5433/gis_test"
    config = explicit_alembic_config(url)
    assert config.attributes["explicit_database_url"] == url


def test_ephemeral_database_lifecycle_succeeds_and_removes_database() -> None:
    base_url = os.environ["TEST_DATABASE_URL"]
    with ephemeral_migration_database(base_url) as (url, identity):
        assert identity.disposable
        with create_engine(url).connect() as connection:
            assert (
                connection.execute(text("select current_database()")).scalar_one()
                == identity.database
            )
