from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from gis.database_safety import destructive_alembic_config, safe_identity
from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    Organization,
    ProviderCollectionPolicy,
    Site,
    SourceType,
    Tenant,
)
from gis.provider_control.service import ProviderControlService


def test_realistic_pre_0029_state_migrates_to_provider_inventory(
    migration_database_url: str,
) -> None:
    identity = safe_identity(migration_database_url, "test", "")
    run_id = identity.database.removeprefix("gis_migration_test_")
    config = destructive_alembic_config(
        migration_database_url,
        environment="test",
        test_run_id=run_id,
        authorization_token=f"gis-destructive-test:{run_id}",
    )
    command.downgrade(config, "20260902_0028")

    engine = create_engine(migration_database_url)
    try:
        with Session(engine) as session:
            tenant = Tenant(name="Migration Regression", slug="provider-migration")
            session.add(tenant)
            session.flush()
            organization = Organization(
                tenant_id=tenant.id, name="Migration Regression", slug="provider-migration"
            )
            session.add(organization)
            session.flush()
            site = Site(
                tenant_id=tenant.id,
                organization_id=organization.id,
                name="Migration Regression",
                slug="provider-migration",
                canonical_url="https://provider-migration.example",
                timezone="America/New_York",
            )
            session.add(site)
            session.flush()
            sources = []
            for key in ("google_search_console", "ga4", "pagespeed", "dataforseo"):
                source = DataSource(
                    key=key,
                    name=key.replace("_", " ").title(),
                    provider="Migration fixture",
                    source_type=(
                        SourceType.COMMERCIAL if key == "dataforseo" else SourceType.PUBLIC
                    ),
                )
                session.add(source)
                session.flush()
                sources.append(source.id)
                session.add(
                    DataSourceConnection(
                        tenant_id=tenant.id,
                        site_id=site.id,
                        data_source_id=source.id,
                        connection_type=ConnectionType.BYOD,
                        status=ConnectionStatus.ACTIVE,
                        credential_reference=f"env:MIGRATION_{key.upper()}",
                    )
                )
            session.commit()
            tenant_id, site_id = tenant.id, site.id

        command.upgrade(config, "head")

        with Session(engine) as session:
            items = {
                item["key"]: item
                for item in ProviderControlService(session).inventory(tenant_id, site_id)["items"]
            }
            assert items["google_search_console"]["collection_state"] == "ACTIVE"
            assert items["ga4"]["collection_state"] == "ACTIVE"
            assert items["google_pagespeed"]["collection_state"] == "ACTIVE"
            assert items["dataforseo"]["connection_state"] == "CONNECTED"
            assert items["dataforseo"]["collection_state"] == "CONNECTED_DISABLED"
            assert items["builtwith"]["collection_state"] == "NOT_CONNECTED"
            assert items["whoisxmlapi"]["collection_state"] == "UNAVAILABLE"

            session.execute(
                delete(ProviderCollectionPolicy).where(
                    ProviderCollectionPolicy.tenant_id == tenant_id
                )
            )
            session.execute(
                delete(DataSourceConnection).where(DataSourceConnection.tenant_id == tenant_id)
            )
            session.execute(delete(Site).where(Site.id == site_id))
            session.execute(delete(Organization).where(Organization.tenant_id == tenant_id))
            session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            session.execute(delete(DataSource).where(DataSource.id.in_(sources)))
            session.commit()
    finally:
        engine.dispose()
