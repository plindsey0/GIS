from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataSource,
    DataSourceConnection,
    Organization,
    ProviderDefinition,
    ProviderPolicyAuditEvent,
    ProviderPricingConfiguration,
    ProviderUsageEvent,
    Site,
    Tenant,
)
from gis.provider_control.service import ProviderControlService
from gis.seed import seed


def scope(session: Session) -> tuple[Tenant, Site, DataSourceConnection]:
    seed(session)
    tenant = Tenant(name="Provider Test", slug="provider-test")
    session.add(tenant)
    session.flush()
    organization = Organization(tenant_id=tenant.id, name="Provider Test", slug="provider-test")
    session.add(organization)
    session.flush()
    site = Site(
        tenant_id=tenant.id,
        organization_id=organization.id,
        name="Provider Test",
        slug="provider-test",
        canonical_url="https://provider-test.example",
        timezone="America/New_York",
    )
    session.add(site)
    session.flush()
    source = session.scalar(select(DataSource).where(DataSource.key == "dataforseo"))
    assert source
    connection = DataSourceConnection(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_id=source.id,
        connection_type=ConnectionType.BYOD,
        status=ConnectionStatus.ACTIVE,
        credential_reference="secret-manager://provider-test/dataforseo",
    )
    session.add(connection)
    session.flush()
    return tenant, site, connection


def configured(session: Session) -> tuple[ProviderControlService, Tenant, Site]:
    tenant, site, connection = scope(session)
    service = ProviderControlService(session)
    service.configure(
        tenant.id,
        site.id,
        "dataforseo",
        {
            "data_source_connection_id": connection.id,
            "monthly_soft_budget": Decimal("8"),
            "monthly_hard_budget": Decimal("10"),
            "daily_hard_budget": Decimal("5"),
            "per_run_hard_budget": Decimal("3"),
            "daily_request_limit": 3,
            "monthly_request_limit": 10,
            "per_run_request_limit": 2,
            "timezone": "America/New_York",
        },
        "test-admin",
        "test setup",
    )
    service.set_capability(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        True,
        "DAILY",
        "test-admin",
    )
    service.add_target(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        "QUERY",
        "va loan calculator",
        "HIGH",
        "test-admin",
    )
    provider = service.provider("dataforseo")
    capability = service.capability(provider.id, "SERP_COLLECTION")
    session.add(
        ProviderPricingConfiguration(
            provider_id=provider.id,
            capability_id=capability.id,
            pricing_model="PER_REQUEST",
            unit_price=Decimal("1.25"),
            units_per_price=Decimal("1"),
            currency="USD",
            provenance="OPERATOR_CONFIGURED",
            effective_start_at=datetime.now(timezone.utc),
        )
    )
    service.transition(tenant.id, site.id, "dataforseo", "ENABLE", "test-admin", None)
    session.flush()
    return service, tenant, site


def test_registry_is_seeded_and_commercial_collection_defaults_off(session: Session) -> None:
    keys = set(session.scalars(select(ProviderDefinition.provider_key)))
    assert {"dataforseo", "semrush", "builtwith", "whoisxmlapi", "ga4"} <= keys
    provider = session.scalar(
        select(ProviderDefinition).where(ProviderDefinition.provider_key == "dataforseo")
    )
    assert provider and provider.is_commercial


def test_connection_does_not_authorize_collection_and_budget_is_required(session: Session) -> None:
    tenant, site, connection = scope(session)
    service = ProviderControlService(session)
    policy = service.configure(
        tenant.id,
        site.id,
        "dataforseo",
        {"data_source_connection_id": connection.id},
        "test-admin",
        None,
    )
    assert policy.master_enabled is False
    with pytest.raises(ValueError, match="monthly hard budget"):
        service.transition(tenant.id, site.id, "dataforseo", "ENABLE", "test-admin", None)


def test_budget_validation_and_unknown_price_fail_closed(session: Session) -> None:
    tenant, site, connection = scope(session)
    service = ProviderControlService(session)
    with pytest.raises(ValueError, match="soft budget"):
        service.configure(
            tenant.id,
            site.id,
            "dataforseo",
            {
                "data_source_connection_id": connection.id,
                "monthly_soft_budget": Decimal("11"),
                "monthly_hard_budget": Decimal("10"),
            },
            "test-admin",
            None,
        )


def test_preflight_enforces_capability_target_cost_and_reserved_spend(session: Session) -> None:
    service, tenant, site = configured(session)
    blocked_target = service.preflight(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        ["unauthorized query"],
        1,
        Decimal("1"),
    )
    assert blocked_target.can_execute is False
    assert "TARGET_NOT_AUTHORIZED" in blocked_target.blocking_reasons

    first = service.preflight(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        ["va loan calculator"],
        1,
        Decimal("2"),
        reserve=True,
    )
    assert first.can_execute and first.estimated_cost == Decimal("2.50")
    assert first.reservation_id
    second = service.preflight(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        ["va loan calculator"],
        1,
        Decimal("2"),
    )
    assert "DAILY_BUDGET_EXHAUSTED" not in second.blocking_reasons
    assert "PER_RUN_BUDGET_EXCEEDED" not in second.blocking_reasons
    third = service.preflight(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        ["va loan calculator"],
        3,
        Decimal("3"),
    )
    assert "PER_RUN_BUDGET_EXCEEDED" in third.blocking_reasons
    assert "DAILY_BUDGET_EXHAUSTED" in third.blocking_reasons
    assert "DAILY_REQUEST_LIMIT_EXCEEDED" in third.blocking_reasons


def test_usage_reconciliation_disable_and_audit_are_append_oriented(session: Session) -> None:
    service, tenant, site = configured(session)
    result = service.preflight(
        tenant.id,
        site.id,
        "dataforseo",
        "SERP_COLLECTION",
        ["va loan calculator"],
        1,
        Decimal("1"),
        reserve=True,
    )
    assert result.reservation_id
    service.reconcile(
        result.reservation_id,
        actual_cost=Decimal("1.10"),
        semantics="PROVIDER_REPORTED",
        status="SUCCEEDED",
    )
    service.transition(tenant.id, site.id, "dataforseo", "DISABLE", "test-admin", "pause spend")
    assert session.scalar(select(func.count()).select_from(ProviderUsageEvent)) == 1
    assert session.scalar(select(func.count()).select_from(ProviderPolicyAuditEvent)) >= 5
    detail = service.detail(tenant.id, site.id, "dataforseo")
    assert detail["collection_state"] == "CONNECTED_DISABLED"
    assert detail["usage"][0]["actual_cost"] == "1.10000000"


def test_period_boundaries_honor_policy_timezone() -> None:
    day, month = ProviderControlService._periods(
        datetime(2026, 9, 2, 3, 30, tzinfo=timezone.utc), "America/New_York"
    )
    assert day == datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
    assert month == datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
