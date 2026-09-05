from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.models import (
    ConnectionStatus,
    ConnectionType,
    DataRightsGrant,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    Domain,
    PermittedUse,
    PipelineDefinition,
    ProviderAccountTelemetry,
    ProviderCapabilityPolicy,
    ProviderCollectionPolicy,
    ProviderCollectionTarget,
    ProviderControlRecoveryIncident,
    ProviderPolicyAuditEvent,
    ProviderPricingConfiguration,
    ProviderUsageEvent,
    RightsDecision,
    RightsStatus,
    ScheduleDefinition,
    ScheduledTarget,
    ScheduleStatus,
    Site,
    Tenant,
    TrackedQuery,
)
from gis.provider_control.incident_recovery import apply_recovery, recovery_plan
from gis.seed import seed


def setup_recovery_state(session: Session) -> tuple[Tenant, Site]:
    seed(session)
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    domain = session.scalar(select(Domain).where(Domain.hostname == "vahomemath.com"))
    assert tenant and site and domain
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="va loan calculator",
        normalized_query="va loan calculator",
    )
    session.add(query)
    rights = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Connection rights — builtwith-review-2026-09-04-v1",
        raw_storage_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        reviewed_at=datetime.now(timezone.utc),
        review_authority="Test operator",
        documented_basis="Fixture reviewed rights",
    )
    session.add(rights)
    session.flush()
    for permitted_use in (
        PermittedUse.RAW_RETENTION,
        PermittedUse.NORMALIZED_RETENTION,
        PermittedUse.INTERNAL_ANALYSIS,
    ):
        session.add(
            DataRightsGrant(
                policy_id=rights.id,
                permitted_use=permitted_use,
                status=RightsStatus.ALLOWED,
                reason="Fixture reviewed rights",
            )
        )
    connections = {}
    for key in ("dataforseo", "builtwith"):
        source = session.scalar(select(DataSource).where(DataSource.key == key))
        assert source
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            rights_policy_id=rights.id,
            connection_type=ConnectionType.BYOD,
            status=ConnectionStatus.ACTIVE,
            credential_reference=f"env:FIXTURE_{key.upper()}",
        )
        session.add(connection)
        connections[key] = connection
    session.flush()
    for key, pipeline_key, status, cron in (
        ("dataforseo", "serp", ScheduleStatus.ENABLED, "0 7 * * 5"),
        ("dataforseo", "external_search", ScheduleStatus.DISABLED, "0 8 * * *"),
        ("builtwith", "builtwith_technology", ScheduleStatus.DISABLED, "0 8 * * *"),
    ):
        pipeline = session.scalar(
            select(PipelineDefinition).where(PipelineDefinition.key == pipeline_key)
        )
        if pipeline is None:
            pipeline = PipelineDefinition(
                key=pipeline_key,
                name=pipeline_key.replace("_", " ").title(),
                handler_key="COLLECTOR_CLI",
                paid_provider=True,
            )
            session.add(pipeline)
            session.flush()
        schedule = ScheduleDefinition(
            tenant_id=tenant.id,
            site_id=site.id,
            pipeline_id=pipeline.id,
            data_source_connection_id=connections[key].id,
            name=f"recovery fixture {key} {pipeline_key}",
            cron_expression=cron,
            timezone="America/New_York",
            status=status,
            next_scheduled_at=(
                datetime(2026, 9, 11, 11, tzinfo=timezone.utc)
                if status == ScheduleStatus.ENABLED
                else None
            ),
            configuration_json={"provider_capability_policy_id": "lost"},
        )
        session.add(schedule)
        session.flush()
        session.add(
            ScheduledTarget(
                tenant_id=tenant.id,
                site_id=site.id,
                schedule_id=schedule.id,
                target_type="QUERY" if pipeline_key == "serp" else "DOMAIN",
                target_key="lost-target",
                active=True,
            )
        )
    session.flush()
    return tenant, site


def test_recovery_dry_run_and_transactional_idempotent_apply(
    session: Session, tmp_path: Path
) -> None:
    tenant, site = setup_recovery_state(session)
    plan = recovery_plan(session)
    assert plan["historical_records_recreated"] == 0
    assert plan["paid_provider_calls"] == 0
    assert plan["builtwith"]["account_telemetry"] == "UNKNOWN_NOT_REFRESHED"
    schedules_before = session.scalar(select(func.count()).select_from(ScheduleDefinition))
    policies_before = session.scalar(select(func.count()).select_from(ProviderCollectionPolicy))
    capability_policies_before = session.scalar(
        select(func.count()).select_from(ProviderCapabilityPolicy)
    )
    backup = tmp_path / "verified.dump"
    backup.write_bytes(b"fixture archive checked by CLI boundary")

    result = apply_recovery(session, str(backup), "0" * 40)
    assert result["status"] == "COMPLETED"
    assert (
        session.scalar(select(func.count()).select_from(ProviderCollectionPolicy))
        == policies_before + 2
    )
    assert (
        session.scalar(select(func.count()).select_from(ProviderCapabilityPolicy))
        == capability_policies_before + 3
    )
    assert session.scalar(select(func.count()).select_from(ProviderCollectionTarget)) == 3
    assert session.scalar(select(func.count()).select_from(ProviderPricingConfiguration)) == 3
    assert session.scalar(select(func.count()).select_from(ProviderPolicyAuditEvent)) == 11
    assert session.scalar(select(func.count()).select_from(ProviderUsageEvent)) == 0
    assert session.scalar(select(func.count()).select_from(ProviderAccountTelemetry)) == 0
    incident = session.scalar(select(ProviderControlRecoveryIncident))
    assert incident and incident.historical_rows_recreated == 0
    assert set(incident.history_completeness.values()) >= {"PARTIAL"}
    assert session.scalar(select(func.count()).select_from(ScheduleDefinition)) == schedules_before
    enabled = session.scalar(
        select(ScheduleDefinition).where(
            ScheduleDefinition.name == "recovery fixture dataforseo serp"
        )
    )
    assert enabled and enabled.next_scheduled_at == datetime(2026, 9, 11, 11, tzinfo=timezone.utc)

    again = apply_recovery(session, str(backup), "0" * 40)
    assert again["status"] == "ALREADY_COMPLETE"
    assert session.scalar(select(func.count()).select_from(ProviderPolicyAuditEvent)) == 11
