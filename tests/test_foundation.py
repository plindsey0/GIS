from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    IngestionRun,
    IngestionStatus,
    Organization,
    RightsDecision,
    Site,
    SourceType,
    Tenant,
)
from gis.seed import SOURCES, seed


def tenant(session: Session, slug: str) -> Tenant:
    item = Tenant(name=slug.title(), slug=slug)
    session.add(item)
    session.flush()
    return item


def organization(session: Session, owner: Tenant, slug: str = "org") -> Organization:
    item = Organization(tenant_id=owner.id, name=slug.title(), slug=slug)
    session.add(item)
    session.flush()
    return item


def site(session: Session, owner: Tenant, org: Organization, slug: str) -> Site:
    item = Site(
        tenant_id=owner.id,
        organization_id=org.id,
        name=slug.title(),
        slug=slug,
        canonical_url=f"https://{slug}.example",
        timezone="UTC",
    )
    session.add(item)
    session.flush()
    return item


def source(session: Session, key: str = "test") -> DataSource:
    item = DataSource(key=key, name=key.title(), provider="Test", source_type=SourceType.MANUAL)
    session.add(item)
    session.flush()
    return item


def test_tenant_creation_and_multiple_tenants(session: Session) -> None:
    first = tenant(session, "first")
    second = tenant(session, "second")
    assert first.id != second.id
    assert session.scalars(select(Tenant)).all() == [first, second]


def test_multiple_sites_per_tenant(session: Session) -> None:
    owner = tenant(session, "multi-site")
    org = organization(session, owner)
    first = site(session, owner, org, "one")
    second = site(session, owner, org, "two")
    assert {first.tenant_id, second.tenant_id} == {owner.id}


def test_source_keys_are_unique(session: Session) -> None:
    source(session, "duplicate")
    session.add(
        DataSource(key="duplicate", name="Again", provider="Test", source_type=SourceType.MANUAL)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_connection_associates_with_tenant_and_site(session: Session) -> None:
    owner = tenant(session, "connection")
    web_site = site(session, owner, organization(session, owner), "web")
    provider = source(session)
    connection = DataSourceConnection(
        tenant_id=owner.id,
        site_id=web_site.id,
        data_source_id=provider.id,
        connection_type=ConnectionType.NATIVE,
        status=ConnectionStatus.ACTIVE,
        configuration_json={"property": "site"},
        credential_reference="secret-manager://gis/test",
    )
    session.add(connection)
    session.flush()
    assert connection.site_id == web_site.id
    assert "secret" not in connection.configuration_json


def test_connection_rejects_site_from_another_tenant(session: Session) -> None:
    first = tenant(session, "connection-first")
    second = tenant(session, "connection-second")
    second_site = site(session, second, organization(session, second), "other")
    provider = source(session)
    session.add(
        DataSourceConnection(
            tenant_id=first.id,
            site_id=second_site.id,
            data_source_id=provider.id,
            connection_type=ConnectionType.NATIVE,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_rights_tri_state_is_preserved(session: Session) -> None:
    policy = DataRightsPolicy(
        name="Mixed rights",
        commercial_use_allowed=RightsDecision.ALLOWED,
        model_training_allowed=RightsDecision.PROHIBITED,
        ai_inference_allowed=RightsDecision.UNKNOWN,
    )
    session.add(policy)
    session.flush()
    session.expire(policy)
    assert policy.commercial_use_allowed is RightsDecision.ALLOWED
    assert policy.model_training_allowed is RightsDecision.PROHIBITED
    assert policy.ai_inference_allowed is RightsDecision.UNKNOWN
    assert policy.raw_storage_allowed is RightsDecision.UNKNOWN


def test_ingestion_runs_record_success_and_failure(session: Session) -> None:
    owner = tenant(session, "runs")
    web_site = site(session, owner, organization(session, owner), "runs-site")
    connection = DataSourceConnection(
        tenant_id=owner.id,
        site_id=web_site.id,
        data_source_id=source(session).id,
        connection_type=ConnectionType.NATIVE,
    )
    session.add(connection)
    session.flush()
    now = datetime.now(timezone.utc)
    succeeded = IngestionRun(
        tenant_id=owner.id,
        site_id=web_site.id,
        data_source_connection_id=connection.id,
        started_at=now,
        completed_at=now,
        status=IngestionStatus.SUCCEEDED,
        records_received=10,
        records_inserted=10,
    )
    failed = IngestionRun(
        tenant_id=owner.id,
        site_id=web_site.id,
        data_source_connection_id=connection.id,
        started_at=now,
        completed_at=now,
        status=IngestionStatus.FAILED,
        error_count=1,
        error_summary="provider unavailable",
    )
    session.add_all([succeeded, failed])
    session.flush()
    assert succeeded.records_inserted == 10
    assert failed.error_count == 1


def test_required_foreign_key_is_enforced(session: Session) -> None:
    session.add(Organization(tenant_id=uuid.uuid4(), name="Orphan", slug="orphan"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_seed_is_idempotent(session: Session) -> None:
    seed(session, hostname="vahomemath.test")
    seed(session, hostname="vahomemath.test")
    assert len(session.scalars(select(Tenant).where(Tenant.slug == "vahomemath")).all()) == 1
    assert len(session.scalars(select(DataSource)).all()) == len(SOURCES)


def test_migration_created_foundation_tables(session: Session) -> None:
    tables = set(inspect(session.connection()).get_table_names(schema="gis_core"))
    assert {
        "tenant",
        "organization",
        "site",
        "domain",
        "data_rights_policy",
        "data_source",
        "data_source_connection",
        "ingestion_run",
    } <= tables
    assert "gsc_search_observation" in inspect(session.connection()).get_table_names(
        schema="gis_raw"
    )
