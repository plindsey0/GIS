from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_provider_control import scope

from gis.models import (
    DataSource,
    DataSourceConnection,
    OrchestrationRun,
    OrchestrationStatus,
    PipelineDefinition,
    ProviderCapabilityPolicy,
    ProviderCollectionTarget,
    ProviderPricingConfiguration,
    ScheduleDefinition,
    ScheduleStatus,
    TrackedQuery,
    TriggerType,
)
from gis.orchestration.service import Orchestrator
from gis.provider_control.binding import execution_arguments, reconcile_schedules
from gis.provider_control.configuration import CollectionConfiguration, ConfigurationService
from gis.provider_control.manual import ManualRequest, manual_run


def setup(session: Session):
    tenant, site, connection = scope(session)
    query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="va loan calculator",
        normalized_query="va loan calculator",
    )
    session.add(query)
    session.flush()
    config = CollectionConfiguration.model_validate(
        {
            "policy": {
                "actor": "test-admin",
                "data_source_connection_id": str(connection.id),
                "monthly_soft_budget": "20",
                "monthly_hard_budget": "30",
                "per_run_hard_budget": "5",
                "daily_request_limit": 20,
                "monthly_request_limit": 100,
                "per_run_request_limit": 1,
                "timezone": "America/New_York",
            },
            "capabilities": [
                {
                    "key": "SERP_COLLECTION",
                    "enabled": True,
                    "target_ids": [str(query.id)],
                    "cadence": "WEEKLY",
                    "weekday": 1,
                    "hour": 8,
                    "unit_price": "0.5",
                }
            ],
        }
    )
    return tenant, site, query, config, ConfigurationService(session)


def test_disabled_save_roundtrip_and_weekly_activation(session: Session) -> None:
    tenant, site, query, config, service = setup(session)
    result = service.save(tenant.id, site.id, "dataforseo", config)
    assert result["preview"]["can_activate"]
    read = service.read(tenant.id, site.id, "dataforseo")
    cap = next(c for c in read["capabilities"] if c["key"] == "SERP_COLLECTION")
    assert cap["target_ids"] == [str(query.id)]
    assert read["detail"]["collection_state"] == "CONNECTED_DISABLED"
    schedule = session.scalar(
        select(ScheduleDefinition).where(ScheduleDefinition.tenant_id == tenant.id)
    )
    assert (
        schedule
        and schedule.status == ScheduleStatus.DISABLED
        and schedule.next_scheduled_at is None
    )
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    assert schedule.status == ScheduleStatus.ENABLED
    assert schedule.cron_expression == "0 8 * * 1" and schedule.timezone == "America/New_York"
    assert schedule.next_scheduled_at and schedule.freshness_sla_seconds == 604800
    due = schedule.next_scheduled_at
    queued = Orchestrator(session).enqueue_due(now=due)
    assert len(queued) == 1
    pipeline = session.get(PipelineDefinition, queued[0].pipeline_id)
    assert pipeline
    assert execution_arguments(session, queued[0], pipeline) == [
        "sync",
        "--connection",
        str(config.policy.data_source_connection_id),
        "--query-id",
        str(query.id),
    ]
    assert Orchestrator(session).enqueue_due(now=due) == []
    assert (
        session.scalar(
            select(func.count())
            .select_from(ScheduleDefinition)
            .where(ScheduleDefinition.tenant_id == tenant.id)
        )
        == 1
    )


def test_scope_unknown_price_and_invalid_timezone(session: Session) -> None:
    tenant, site, query, config, service = setup(session)
    config.capabilities[0].target_ids = [uuid.uuid4()]
    with pytest.raises(ValueError, match="canonical site scope"):
        service.preview(tenant.id, site.id, "dataforseo", config)
    config.capabilities[0].target_ids = [query.id]
    config.capabilities[0].unit_price = None
    assert not service.preview(tenant.id, site.id, "dataforseo", config)["can_activate"]
    config.policy.allow_unknown_cost = True
    assert service.preview(tenant.id, site.id, "dataforseo", config)["can_activate"]
    config.policy.timezone = "Invalid/Timezone"
    with pytest.raises(ValueError, match="timezone"):
        service.preview(tenant.id, site.id, "dataforseo", config)


def test_removed_target_and_disabled_policy_block_dispatch(session: Session) -> None:
    tenant, site, query, config, service = setup(session)
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    cp = session.scalar(
        select(ProviderCapabilityPolicy)
        .join(ProviderCollectionTarget)
        .where(ProviderCollectionTarget.target_reference_id == query.id)
    )
    assert cp
    target = session.scalar(
        select(ProviderCollectionTarget).where(
            ProviderCollectionTarget.capability_policy_id == cp.id
        )
    )
    pipeline = session.scalar(select(PipelineDefinition).where(PipelineDefinition.key == "serp"))
    schedule = session.scalar(
        select(ScheduleDefinition).where(ScheduleDefinition.tenant_id == tenant.id)
    )
    assert target and pipeline and schedule
    run = OrchestrationRun(
        tenant_id=tenant.id,
        site_id=site.id,
        pipeline_id=pipeline.id,
        schedule_id=schedule.id,
        data_source_connection_id=config.policy.data_source_connection_id,
        trigger_type=TriggerType.SCHEDULED,
        status=OrchestrationStatus.PENDING,
        configuration_json={**schedule.configuration_json, "provider_target_id": str(target.id)},
    )
    session.add(run)
    session.flush()
    assert "--query-id" in (execution_arguments(session, run, pipeline) or [])
    query.active = False
    with pytest.raises(ValueError, match="Canonical target"):
        execution_arguments(session, run, pipeline)
    query.active = True
    target.enabled = False
    with pytest.raises(ValueError, match="no longer authorized"):
        execution_arguments(session, run, pipeline)
    target.enabled = True
    policy = service.control.transition(tenant.id, site.id, "dataforseo", "PAUSE", "test", None)
    reconcile_schedules(session, policy)
    assert run.status == OrchestrationStatus.CANCELLED
    with pytest.raises(ValueError, match="disabled or paused"):
        execution_arguments(session, run, pipeline)


def test_manual_preview_confirmation_idempotency_and_current_policy(session: Session) -> None:
    tenant, site, _, config, service = setup(session)
    service.save(tenant.id, site.id, "dataforseo", config)
    request = ManualRequest(request_id=uuid.uuid4())
    preview = manual_run(session, tenant.id, site.id, "dataforseo", request)
    assert preview["blockers"] and preview["paid_calls_made"] == 0
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    preview = manual_run(session, tenant.id, site.id, "dataforseo", request)
    assert preview["blockers"] == [] and preview["requests"] == 1
    assert session.scalar(select(func.count()).select_from(OrchestrationRun)) == 0
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    assert manual_run(session, tenant.id, site.id, "dataforseo", request)["queued"] == 1
    assert manual_run(session, tenant.id, site.id, "dataforseo", request)["queued"] == 0
    config.policy.monthly_hard_budget = Decimal("31")
    service.save(tenant.id, site.id, "dataforseo", config)
    assert session.scalar(select(OrchestrationRun.status)) == OrchestrationStatus.CANCELLED
    with pytest.raises(ValueError, match="changed after preview"):
        manual_run(session, tenant.id, site.id, "dataforseo", request)


def test_scoped_pricing_never_leaks_to_other_tenants(session: Session) -> None:
    tenant, site, _, config, service = setup(session)
    service.save(tenant.id, site.id, "dataforseo", config)
    provider = service.control.provider("dataforseo")
    cap = service.control.capability(provider.id, "SERP_COLLECTION")
    assert service.control._pricing(provider.id, cap.id, tenant.id, site.id).unit_price == Decimal(
        "0.5"
    )
    assert service.control._pricing(provider.id, cap.id, uuid.uuid4(), uuid.uuid4()) is None
    assert session.scalar(select(func.count()).select_from(ProviderPricingConfiguration)) == 1


def test_pagespeed_lab_and_field_share_one_schedule(session: Session) -> None:
    tenant, site, _, config, service = setup(session)
    connection = session.get(DataSourceConnection, config.policy.data_source_connection_id)
    source = session.scalar(select(DataSource).where(DataSource.key == "pagespeed"))
    assert connection and source
    connection.data_source_id = source.id
    config.capabilities = [
        config.capabilities[0].model_copy(
            update={"key": key, "target_ids": [site.id], "unit_price": None}
        )
        for key in ("LAB_PERFORMANCE", "FIELD_CRUX")
    ]
    config.activate = True
    result = service.save(tenant.id, site.id, "google_pagespeed", config)
    assert result["preview"]["estimated_requests_month"] == "4.345"
    assert (
        session.scalar(
            select(func.count())
            .select_from(ScheduleDefinition)
            .where(ScheduleDefinition.tenant_id == tenant.id)
        )
        == 1
    )
    config.capabilities[1].hour = 9
    assert not service.preview(tenant.id, site.id, "google_pagespeed", config)["can_activate"]
