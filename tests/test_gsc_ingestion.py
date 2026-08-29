from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gis.integrations.gsc.cli import configure_connection
from gis.integrations.gsc.client import GSCClient
from gis.integrations.gsc.config import CollectionGrain
from gis.integrations.gsc.service import (
    GSCCollector,
    date_chunks,
    normalize_row,
    validate_connection,
)
from gis.models import (
    ConnectionStatus,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    GSCSearchObservation,
    IngestionRun,
    IngestionStatus,
    Organization,
    RightsDecision,
    Site,
    Tenant,
)
from gis.seed import seed


def provider_row(
    observed: str = "2026-08-20",
    *,
    clicks: float = 25,
    query: str | None = "va loan calculator",
    page: str | None = "https://vahomemath.test/va-loan-calculator/",
) -> dict[str, Any]:
    return {
        "keys": [observed, query, page],
        "clicks": clicks,
        "impressions": 410.25,
        "ctr": 0.0609756098,
        "position": 7.2,
    }


class DateTransport:
    def __init__(
        self,
        rows: dict[str, list[dict[str, Any]]],
        *,
        fail_dates: set[str] | None = None,
    ) -> None:
        self.rows = rows
        self.fail_dates = fail_dates or set()
        self.calls: list[tuple[str, int]] = []

    def query(self, property_uri: str, body: dict[str, Any]) -> dict[str, Any]:
        day = body["startDate"]
        self.calls.append((day, body["startRow"]))
        if day in self.fail_dates:
            raise RuntimeError("test provider failure")
        all_rows = self.rows.get(day, [])
        start = body["startRow"]
        limit = body["rowLimit"]
        return {"rows": all_rows[start : start + limit]}

    def list_sites(self) -> list[dict[str, Any]]:
        return [{"siteUrl": "sc-domain:vahomemath.test"}]


def setup_connection(
    session: Session,
    *,
    property_uri: str = "sc-domain:vahomemath.test",
) -> DataSourceConnection:
    seed(session, hostname="vahomemath.test")
    connection = configure_connection(
        session,
        tenant_slug="vahomemath",
        site_slug="vahomemath",
        property_uri=property_uri,
        credential_reference="env:GSC_TEST_CREDENTIALS",
        auth_mode="service_account",
        grain=CollectionGrain.QUERY_PAGE,
        search_type="web",
    )
    connection.status = ConnectionStatus.ACTIVE
    session.commit()
    return connection


def collector(
    session: Session, connection: DataSourceConnection, transport: DateTransport
) -> GSCCollector:
    return GSCCollector(session, GSCClient(transport, row_limit=1))


def test_response_normalization_preserves_values_and_numeric_fidelity(session: Session) -> None:
    connection = setup_connection(session)
    source = session.get(DataSource, connection.data_source_id)
    assert source is not None and connection.site_id is not None
    config = validate_connection(connection, source)
    row = normalize_row(
        provider_row(),
        config,
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        connection_id=connection.id,
        requested_date=date(2026, 8, 20),
    )
    assert row.query == "va loan calculator"
    assert row.page == "https://vahomemath.test/va-loan-calculator/"
    assert row.impressions == Decimal("410.25")
    assert row.ctr == Decimal("0.0609756098")


def test_null_query_is_preserved_where_allowed(session: Session) -> None:
    connection = setup_connection(session)
    source = session.get(DataSource, connection.data_source_id)
    assert source is not None and connection.site_id is not None
    row = normalize_row(
        provider_row(query=None),
        validate_connection(connection, source),
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        connection_id=connection.id,
        requested_date=date(2026, 8, 20),
    )
    assert row.query is None


def test_successful_ingestion_creates_run_and_paginated_observations(session: Session) -> None:
    connection = setup_connection(session)
    transport = DateTransport(
        {"2026-08-20": [provider_row(), provider_row(query="va mortgage calculator")]}
    )
    run = collector(session, connection, transport).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    assert run.status is IngestionStatus.SUCCEEDED
    assert (run.records_received, run.records_inserted, run.records_rejected) == (2, 2, 0)
    assert len(transport.calls) == 3
    assert session.scalar(select(func.count()).select_from(GSCSearchObservation)) == 2


def test_page_daily_grain_ingests_without_query(session: Session) -> None:
    connection = setup_connection(session)
    connection.configuration_json = {
        **connection.configuration_json,
        "collection_grain": "page",
    }
    session.commit()
    page_row = {
        "keys": ["2026-08-20", "https://vahomemath.test/page/"],
        "clicks": 10,
        "impressions": 100,
        "ctr": 0.1,
        "position": 4.5,
    }
    run = collector(session, connection, DateTransport({"2026-08-20": [page_row]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    observation = session.scalar(select(GSCSearchObservation))
    assert run.status is IngestionStatus.SUCCEEDED
    assert observation is not None and observation.query is None
    assert observation.collection_grain == "page"


def test_first_chunk_failure_marks_run_failed(session: Session) -> None:
    connection = setup_connection(session)
    run = collector(session, connection, DateTransport({}, fail_dates={"2026-08-20"})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    assert run.status is IngestionStatus.FAILED
    assert run.error_count == 1


def test_malformed_row_is_rejected_and_counted(session: Session) -> None:
    connection = setup_connection(session)
    malformed = provider_row()
    malformed["clicks"] = "not-a-number"
    run = collector(session, connection, DateTransport({"2026-08-20": [malformed]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    assert run.status is IngestionStatus.PARTIAL
    assert (run.records_received, run.records_inserted, run.records_rejected) == (1, 0, 1)


def test_later_chunk_failure_retains_work_and_marks_partial(session: Session) -> None:
    connection = setup_connection(session)
    run = collector(
        session,
        connection,
        DateTransport({"2026-08-20": [provider_row()]}, fail_dates={"2026-08-21"}),
    ).sync(connection.id, date(2026, 8, 20), date(2026, 8, 21))
    assert run.status is IngestionStatus.PARTIAL
    assert run.records_inserted == 1
    assert session.scalar(select(func.count()).select_from(GSCSearchObservation)) == 1


def test_identical_rerun_does_not_duplicate_logical_observation(session: Session) -> None:
    connection = setup_connection(session)
    rows = {"2026-08-20": [provider_row()]}
    first = collector(session, connection, DateTransport(rows)).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    second = collector(session, connection, DateTransport(rows)).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    assert first.records_inserted == 1
    assert second.records_inserted == 0
    assert session.scalar(select(func.count()).select_from(GSCSearchObservation)) == 1


def test_provider_revision_closes_old_version_and_appends_new(session: Session) -> None:
    connection = setup_connection(session)
    collector(session, connection, DateTransport({"2026-08-20": [provider_row(clicks=25)]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    collector(session, connection, DateTransport({"2026-08-20": [provider_row(clicks=26)]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    versions = session.scalars(
        select(GSCSearchObservation).order_by(GSCSearchObservation.effective_start)
    ).all()
    assert len(versions) == 2
    assert versions[0].effective_end is not None
    assert versions[1].effective_end is None
    assert versions[1].clicks == Decimal("26.000000")


def test_backfill_chunks_each_day_and_rerun_is_safe(session: Session) -> None:
    connection = setup_connection(session)
    rows = {
        "2026-08-20": [provider_row("2026-08-20")],
        "2026-08-21": [provider_row("2026-08-21")],
    }
    first_transport = DateTransport(rows)
    first = collector(session, connection, first_transport).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 21)
    )
    second = collector(session, connection, DateTransport(rows)).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 21)
    )
    assert first.records_inserted == 2
    assert second.records_inserted == 0
    assert {day for day, _ in first_transport.calls} == {"2026-08-20", "2026-08-21"}


def test_failed_chunk_can_be_rerun_safely(session: Session) -> None:
    connection = setup_connection(session)
    rows = {
        "2026-08-20": [provider_row("2026-08-20")],
        "2026-08-21": [provider_row("2026-08-21")],
    }
    collector(session, connection, DateTransport(rows, fail_dates={"2026-08-21"})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 21)
    )
    rerun = collector(session, connection, DateTransport(rows)).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 21)
    )
    assert rerun.records_inserted == 1
    assert session.scalar(select(func.count()).select_from(GSCSearchObservation)) == 2


def test_connection_override_rights_policy_is_stored(session: Session) -> None:
    connection = setup_connection(session)
    policy = DataRightsPolicy(
        tenant_id=connection.tenant_id,
        name="Tenant GSC policy",
        raw_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add(policy)
    session.flush()
    connection.rights_policy_id = policy.id
    session.commit()
    collector(session, connection, DateTransport({"2026-08-20": [provider_row()]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    observation = session.scalar(select(GSCSearchObservation))
    assert observation is not None
    assert observation.rights_policy_id == policy.id
    assert policy.raw_storage_allowed is RightsDecision.ALLOWED
    assert policy.model_training_allowed is RightsDecision.UNKNOWN


def test_default_unknown_rights_policy_is_used(session: Session) -> None:
    connection = setup_connection(session)
    collector(session, connection, DateTransport({"2026-08-20": [provider_row()]})).sync(
        connection.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    observation = session.scalar(select(GSCSearchObservation))
    assert observation is not None
    policy = session.get(DataRightsPolicy, observation.rights_policy_id)
    assert policy is not None
    assert policy.commercial_use_allowed is RightsDecision.UNKNOWN


def test_two_tenants_ingest_same_shaped_property_independently(session: Session) -> None:
    first = setup_connection(session)
    source = session.get(DataSource, first.data_source_id)
    assert source is not None
    second_tenant = Tenant(name="Second", slug="second")
    session.add(second_tenant)
    session.flush()
    second_org = Organization(tenant_id=second_tenant.id, name="Second", slug="second")
    session.add(second_org)
    session.flush()
    second_site = Site(
        tenant_id=second_tenant.id,
        organization_id=second_org.id,
        name="Second",
        slug="second",
        canonical_url="https://vahomemath.test",
        timezone="UTC",
    )
    session.add(second_site)
    session.flush()
    second = DataSourceConnection(
        tenant_id=second_tenant.id,
        site_id=second_site.id,
        data_source_id=source.id,
        connection_type=first.connection_type,
        status=ConnectionStatus.ACTIVE,
        external_account_id=first.external_account_id,
        configuration_json=first.configuration_json,
        credential_reference="env:SECOND_TEST_CREDENTIALS",
    )
    session.add(second)
    session.commit()
    rows = {"2026-08-20": [provider_row()]}
    collector(session, first, DateTransport(rows)).sync(
        first.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    collector(session, second, DateTransport(rows)).sync(
        second.id, date(2026, 8, 20), date(2026, 8, 20)
    )
    observations = session.scalars(select(GSCSearchObservation)).all()
    assert len(observations) == 2
    assert observations[0].observation_key != observations[1].observation_key


def test_database_rejects_cross_tenant_observation_scope(session: Session) -> None:
    connection = setup_connection(session)
    other = Tenant(name="Other", slug="other-scope")
    session.add(other)
    session.flush()
    run = IngestionRun(
        tenant_id=connection.tenant_id,
        site_id=connection.site_id,
        data_source_connection_id=connection.id,
        started_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        status=IngestionStatus.RUNNING,
    )
    session.add(run)
    session.flush()
    source = session.get(DataSource, connection.data_source_id)
    assert source is not None and source.default_rights_policy_id is not None
    session.add(
        GSCSearchObservation(
            tenant_id=other.id,
            site_id=connection.site_id,
            data_source_connection_id=connection.id,
            ingestion_run_id=run.id,
            rights_policy_id=source.default_rights_policy_id,
            observation_key="x" * 64,
            collection_grain="query-page",
            observed_date=date(2026, 8, 20),
            page="https://example.test",
            page_hash="x" * 64,
            search_type="web",
            clicks=Decimal("0"),
            impressions=Decimal("1"),
            ctr=Decimal("0"),
            position=Decimal("1"),
            observed_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
            effective_start=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_date_range_chunking_is_one_day_per_request() -> None:
    assert date_chunks(date(2026, 8, 20), date(2026, 8, 22)) == [
        (date(2026, 8, 20), date(2026, 8, 20)),
        (date(2026, 8, 21), date(2026, 8, 21)),
        (date(2026, 8, 22), date(2026, 8, 22)),
    ]
