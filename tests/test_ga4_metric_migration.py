from __future__ import annotations

import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://gis:gis@localhost:5432/gis_test"
)


def _column_names() -> set[str]:
    engine = create_engine(TEST_DATABASE_URL)
    try:
        return {
            column["name"]
            for column in inspect(engine).get_columns("ga4_event_observation", schema="gis_raw")
        }
    finally:
        engine.dispose()


def _check_names() -> set[str]:
    engine = create_engine(TEST_DATABASE_URL)
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


def test_ga4_metric_migration_upgrade_and_downgrade(migrated_database: None) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)

    assert "event_count_per_user" in _column_names()
    assert "ck_ga4_event_event_count_per_user_nonnegative" in _check_names()

    command.downgrade(config, "20260829_0004")
    assert "event_count_per_active_user" in _column_names()
    assert "event_count_per_user" not in _column_names()
    assert "ck_ga4_event_event_count_per_active_user_nonnegative" in _check_names()

    command.upgrade(config, "head")
    assert "event_count_per_user" in _column_names()
    assert "event_count_per_active_user" not in _column_names()
    assert "ck_ga4_event_event_count_per_user_nonnegative" in _check_names()
