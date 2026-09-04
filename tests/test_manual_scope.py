import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from test_provider_configuration import setup

from gis.api.system import SystemQueries
from gis.models import (
    Domain,
    OrchestrationRun,
    ProviderCollectionTarget,
    ProviderUsageEvent,
    ScheduleDefinition,
)
from gis.provider_control.binding import execution_arguments, schedules_for
from gis.provider_control.configuration import CapabilityConfiguration
from gis.provider_control.manual import ManualRequest, manual_run


def configured(session):
    tenant, site, query, config, service = setup(session)
    from gis.models import DataRightsPolicy, DataSourceConnection, RightsDecision

    rights = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Manual fixture rights",
        derived_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add(rights)
    session.flush()
    session.get(
        DataSourceConnection, config.policy.data_source_connection_id
    ).rights_policy_id = rights.id
    domain = Domain(tenant_id=tenant.id, site_id=site.id, hostname="vahomemath.com")
    session.add(domain)
    session.flush()
    config.capabilities.append(
        CapabilityConfiguration(
            key="DOMAIN_SEARCH_INTELLIGENCE",
            enabled=True,
            target_ids=[domain.id],
            cadence="MANUAL_ONLY",
        )
    )
    config.policy.allow_unknown_cost = True
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    return tenant, site, service


def invoke(session, tenant, site, request):
    return manual_run(session, tenant.id, site.id, "dataforseo", request)


def test_explicit_scope_excludes_scheduled_target_and_preserves_schedule(session):
    tenant, site, service = configured(session)
    request = ManualRequest(request_id=uuid.uuid4())
    options = invoke(session, tenant, site, request)
    assert options["requests"] == 0 and options["scope"] == [] and len(options["choices"]) == 2
    domain = next(
        c for c in options["choices"] if c["capability_key"] == "DOMAIN_SEARCH_INTELLIGENCE"
    )
    serp = next(c for c in options["choices"] if c["capability_key"] == "SERP_COLLECTION")
    assert not domain["default_selected"] and not serp["default_selected"]
    snapshots = [
        (s.id, s.cron_expression, s.next_scheduled_at, s.status, s.policy_version)
        for s in session.scalars(select(ScheduleDefinition))
    ]
    request.target_ids = [uuid.UUID(domain["id"])]
    preview = invoke(session, tenant, site, request)
    assert (preview["capabilities"], preview["targets"], preview["requests"]) == (1, 1, 1)
    assert preview["estimated_cost"] is None and not preview["blockers"]
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    assert invoke(session, tenant, site, request)["queued"] == 1
    run = session.scalar(select(OrchestrationRun))
    assert run.schedule_id is None and run.trigger_type.value == "MANUAL"
    assert run.configuration_json["provider_target_id"] == domain["id"]
    assert run.configuration_json["manual_execution_scope"]["target_ids"] == [domain["id"]]
    assert run.configuration_json["manual_execution_scope"]["actor"] == "workbench-admin"
    from gis.models import PipelineDefinition

    assert (
        execution_arguments(session, run, session.get(PipelineDefinition, run.pipeline_id))[-1]
        == "vahomemath.com"
    )
    for status in ["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]:
        from gis.models import OrchestrationStatus

        run.status = OrchestrationStatus(status)
        detail = SystemQueries(session).run_detail(run.id, tenant.id, site.id)
        assert detail["capability_name"] and detail["target_display_name"] == "vahomemath.com"
        assert detail["request_count"] == 1
    assert snapshots == [
        (s.id, s.cron_expression, s.next_scheduled_at, s.status, s.policy_version)
        for s in session.scalars(select(ScheduleDefinition))
    ]
    assert list(session.scalars(select(ProviderUsageEvent))) == []
    assert invoke(session, tenant, site, request)["queued"] == 0
    schedules = schedules_for(
        session, tenant.id, site.id, service.control.provider("dataforseo").id
    )
    assert any(s["cadence"] == "MANUAL_ONLY" and s["next_at"] is None for s in schedules)


@pytest.mark.parametrize(
    "change",
    [
        "target_disabled",
        "capability_disabled",
        "unauthorized",
        "paused",
        "disabled",
        "daily_limit",
        "per_run_limit",
        "rights",
        "monthly_limit",
        "budget",
        "unknown_cost",
    ],
)
def test_scope_cannot_bypass_controls(session, change):
    tenant, site, service = configured(session)
    options = invoke(session, tenant, site, ManualRequest(request_id=uuid.uuid4()))
    choice = next(c for c in options["choices"] if c["capability_key"] == "SERP_COLLECTION")
    target = session.get(ProviderCollectionTarget, uuid.UUID(choice["id"]))
    policy = service.control.policy(tenant.id, site.id, service.control.provider("dataforseo").id)
    request = ManualRequest(request_id=uuid.uuid4(), target_ids=[target.id])
    if change == "target_disabled":
        target.enabled = False
    elif change == "capability_disabled":
        from gis.models import ProviderCapabilityPolicy

        session.get(ProviderCapabilityPolicy, target.capability_policy_id).enabled = False
    elif change == "unauthorized":
        request.target_ids = [uuid.uuid4()]
    elif change == "paused":
        policy.status = "PAUSED"
    elif change == "disabled":
        policy.master_enabled = False
    elif change == "daily_limit":
        policy.daily_request_limit = 0
    elif change == "per_run_limit":
        policy.per_run_request_limit = 0
    elif change == "rights":
        from gis.models import DataRightsPolicy, DataSourceConnection, RightsDecision

        connection = session.get(DataSourceConnection, policy.data_source_connection_id)
        session.get(
            DataRightsPolicy, connection.rights_policy_id
        ).derived_storage_allowed = RightsDecision.PROHIBITED
    elif change == "monthly_limit":
        policy.monthly_request_limit = 0
    elif change == "budget":
        policy.per_run_hard_budget = Decimal("0.01")
    elif change == "unknown_cost":
        policy.allow_unknown_cost = False
        request.target_ids = [
            uuid.UUID(
                next(
                    c["id"]
                    for c in options["choices"]
                    if c["capability_key"] == "DOMAIN_SEARCH_INTELLIGENCE"
                )
            )
        ]
    preview = invoke(session, tenant, site, request)
    assert preview["blockers"]
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    with pytest.raises(ValueError):
        invoke(session, tenant, site, request)
    assert list(session.scalars(select(OrchestrationRun))) == []


def test_scope_change_requires_new_preview_and_multi_capability_totals(session):
    tenant, site, _ = configured(session)
    request = ManualRequest(request_id=uuid.uuid4())
    choices = invoke(session, tenant, site, request)["choices"]
    request.target_ids = [uuid.UUID(choices[0]["id"])]
    preview = invoke(session, tenant, site, request)
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    request.target_ids = [uuid.UUID(c["id"]) for c in choices]
    with pytest.raises(ValueError, match="changed after preview"):
        invoke(session, tenant, site, request)
    request.confirmed = False
    both = invoke(session, tenant, site, request)
    assert (both["capabilities"], both["targets"], both["requests"]) == (2, 2, 2)
    request.confirmed, request.fingerprint = True, both["fingerprint"]
    assert invoke(session, tenant, site, request)["queued"] == 2
    assert len(list(session.scalars(select(OrchestrationRun)))) == 2


def test_multiple_targets_within_capability_and_request_identity(session):
    tenant, site, _ = configured(session)
    request = ManualRequest(request_id=uuid.uuid4())
    choices = invoke(session, tenant, site, request)["choices"]
    target = session.get(
        ProviderCollectionTarget,
        uuid.UUID(
            next(c["id"] for c in choices if c["capability_key"] == "DOMAIN_SEARCH_INTELLIGENCE")
        ),
    )
    domain = Domain(tenant_id=tenant.id, site_id=site.id, hostname="second.example")
    session.add(domain)
    session.flush()
    second = ProviderCollectionTarget(
        capability_policy_id=target.capability_policy_id,
        target_type="DOMAIN",
        target_value=domain.hostname,
        target_reference_id=domain.id,
        enabled=True,
    )
    session.add(second)
    session.flush()
    request.target_ids = [target.id, second.id]
    preview = invoke(session, tenant, site, request)
    assert (preview["capabilities"], preview["targets"], preview["requests"]) == (1, 2, 2)
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    assert invoke(session, tenant, site, request)["queued"] == 2
    assert {
        r.configuration_json["provider_target_id"]
        for r in session.scalars(select(OrchestrationRun))
    } == {str(target.id), str(second.id)}
    request.confirmed = False
    request.target_ids = [target.id]
    changed = invoke(session, tenant, site, request)
    request.confirmed, request.fingerprint = True, changed["fingerprint"]
    with pytest.raises(ValueError, match="already used"):
        invoke(session, tenant, site, request)
