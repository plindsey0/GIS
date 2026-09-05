from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from gis.database_safety import destructive_alembic_config, safe_identity


def _column_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {
            column["name"]
            for column in inspect(engine).get_columns("ga4_event_observation", schema="gis_raw")
        }
    finally:
        engine.dispose()


def _check_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints(
                "ga4_event_observation", schema="gis_raw"
            )
            if constraint["name"] is not None
        }
    finally:
        engine.dispose()


def test_ga4_metric_migration_upgrade_and_downgrade(migration_database_url: str) -> None:
    identity = safe_identity(migration_database_url, "test", "")
    run_id = identity.database.removeprefix("gis_migration_test_")
    config = destructive_alembic_config(
        migration_database_url,
        environment="test",
        test_run_id=run_id,
        authorization_token=f"gis-destructive-test:{run_id}",
    )

    assert "event_count_per_user" in _column_names(migration_database_url)
    assert "ck_ga4_event_event_count_per_user_nonnegative" in _check_names(migration_database_url)

    command.downgrade(config, "20260829_0004")
    assert "event_count_per_active_user" in _column_names(migration_database_url)
    assert "event_count_per_user" not in _column_names(migration_database_url)
    assert "ck_ga4_event_event_count_per_active_user_nonnegative" in _check_names(
        migration_database_url
    )

    command.upgrade(config, "head")
    assert "event_count_per_user" in _column_names(migration_database_url)
    assert "event_count_per_active_user" not in _column_names(migration_database_url)
    assert "ck_ga4_event_event_count_per_user_nonnegative" in _check_names(migration_database_url)
