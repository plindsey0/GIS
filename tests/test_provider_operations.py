from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_provider_configuration import setup

from gis.api.system import SystemQueries
from gis.models import (
    DataSourceConnection,
    ExecutionAttempt,
    FailureCategory,
    IngestionRun,
    ObligationStatus,
    OrchestrationObligation,
    OrchestrationStatus,
    ProviderUsageEvent,
    ScheduleDefinition,
    TriggerType,
)
from gis.orchestration.service import Orchestrator
from gis.provider_control.operations import (
    authentication,
    provider_operations,
    run_evidence,
    timing,
)


def recovered(session: Session):
    tenant, site, query, config, service = setup(session)
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    schedule = session.scalar(
        select(ScheduleDefinition).where(ScheduleDefinition.tenant_id == tenant.id)
    )
    now = datetime.now(timezone.utc) - timedelta(hours=8)
    schedule.next_scheduled_at = now
    run = Orchestrator(session).enqueue_due(now)[0]
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    run.started_at = now
    run.completed_at = now + timedelta(hours=7, seconds=10)
    run.status = OrchestrationStatus.SUCCEEDED
    obligation.status = ObligationStatus.SATISFIED
    obligation.satisfied_at = run.completed_at
    ingestion = IngestionRun(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_connection_id=run.data_source_connection_id,
        started_at=run.completed_at - timedelta(seconds=9),
        completed_at=run.completed_at,
        status="SUCCEEDED",
        records_received=99,
        records_inserted=99,
        source_metadata={"provider_task_id": "fixture-task", "provider_cost": "0.018"},
    )
    session.add(ingestion)
    session.flush()
    run.ingestion_run_id = ingestion.id
    obligation.ingestion_run_id = ingestion.id
    attempts = [
        ExecutionAttempt(
            orchestration_run_id=run.id,
            attempt_number=1,
            trigger_type=TriggerType.SCHEDULED,
            status=OrchestrationStatus.FAILED,
            worker_id="fixture",
            started_at=now,
            completed_at=now + timedelta(seconds=1),
            failure_category=FailureCategory.INTERNAL_PROCESSING_ERROR,
            error_classification="RuntimeError",
            error_detail='{"error":"referenced credential is unavailable"}',
        ),
        ExecutionAttempt(
            orchestration_run_id=run.id,
            attempt_number=2,
            trigger_type=TriggerType.RETRY,
            status=OrchestrationStatus.SUCCEEDED,
            worker_id="fixture",
            started_at=run.completed_at - timedelta(seconds=9),
            completed_at=run.completed_at,
            ingestion_run_id=ingestion.id,
        ),
    ]
    session.add_all(attempts)
    session.flush()
    connection = session.get(DataSourceConnection, run.data_source_connection_id)
    return tenant, site, run, obligation, attempts, ingestion, connection, service


def test_timing_excludes_recovery_wait_and_preserves_original_failure(session: Session):
    tenant, site, run, obligation, attempts, ingestion, connection, service = recovered(session)
    result = timing(attempts, run, obligation)
    assert result["active_execution_duration"] == 10
    assert result["successful_attempt_duration"] == 9
    assert result["recovery_latency"] == result["obligation_lateness"] == 25210
    assert result["wall_clock_resolution_time"] == 25210
    detail = SystemQueries(session).run_detail(run.id, tenant.id, site.id)
    assert detail["duration_seconds"] == 10 and detail["outcome"] == "RECOVERED"
    assert detail["attempt_timeline"][0]["recorded_classification"] == "RuntimeError"
    assert "could not resolve" in detail["failure_summary"]
    assert detail["provider_href"] == "/providers/dataforseo"
    assert detail["target_display_name"] == "va loan calculator"
    ops = provider_operations(session, connection.id, tenant.id, site.id)
    assert ops["current_incidents"] == 0 and len(ops["activity"]) == 1
    assert ops["reliability"]["recovered_late"] == 1
    obligation.status = ObligationStatus.FAILED
    obligation.satisfied_at = None
    session.flush()
    assert provider_operations(session, connection.id, tenant.id, site.id)["current_incidents"] == 1


def test_authentication_requires_provider_evidence_and_later_failure_supersedes(session: Session):
    _, _, run, _, attempts, ingestion, connection, _ = recovered(session)
    assert authentication(session, connection)["authentication_state"] == "VALIDATED"
    ingestion.source_metadata = {}
    session.flush()
    assert (
        authentication(session, connection)["authentication_state"] == "NOT_INDEPENDENTLY_VALIDATED"
    )
    ingestion.source_metadata = {"provider_task_id": "fixture-task"}
    session.flush()
    session.add(
        ExecutionAttempt(
            orchestration_run_id=run.id,
            attempt_number=3,
            trigger_type=TriggerType.RETRY,
            status=OrchestrationStatus.FAILED,
            worker_id="fixture",
            started_at=run.completed_at + timedelta(seconds=1),
            completed_at=run.completed_at + timedelta(seconds=2),
            failure_category=FailureCategory.AUTHENTICATION_FAILED,
        )
    )
    session.flush()
    assert authentication(session, connection)["authentication_state"] == "AUTHENTICATION_FAILED"


def test_decimal_actual_cost_and_links(session: Session):
    tenant, site, run, _, _, ingestion, connection, service = recovered(session)
    provider = service.control.provider("dataforseo")
    for _ in range(3):
        session.add(
            ProviderUsageEvent(
                tenant_id=tenant.id,
                site_id=site.id,
                provider_id=provider.id,
                data_source_connection_id=connection.id,
                ingestion_run_id=ingestion.id,
                occurred_at=run.completed_at,
                request_count=1,
                unit_count=Decimal(1),
                unit_type="REQUEST",
                actual_cost=Decimal("0.018"),
                currency="USD",
                cost_semantics="PROVIDER_REPORTED",
                status="SUCCEEDED",
            )
        )
    session.flush()
    evidence = run_evidence(session, run)
    assert Decimal(evidence["provider_cost_exact"]) == Decimal("0.054")
    assert evidence["provider_cost_display"] == "0.05"
    assert len(evidence["cost_links"]) == 3
    assert all(
        u.actual_cost == Decimal("0.018")
        for u in session.scalars(
            select(ProviderUsageEvent).where(ProviderUsageEvent.ingestion_run_id == ingestion.id)
        )
    )


def test_incomplete_attempt_is_unknown_not_wall_clock_runtime(session: Session):
    _, _, run, obligation, attempts, _, _, _ = recovered(session)
    attempts[-1].completed_at = None
    assert timing(attempts, run, obligation)["active_execution_duration"] is None


def test_rights_health_and_filters_use_scoped_evidence(session: Session, monkeypatch):
    import gis.provider_control.runtime as runtime
    from gis.models import DataRightsPolicy, RightsDecision

    tenant, site, run, obligation, _, _, connection, service = recovered(session)
    rights = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Recorded fixture rights",
        raw_storage_allowed=RightsDecision.ALLOWED,
        deterministic_analysis_allowed=RightsDecision.UNKNOWN,
    )
    session.add(rights)
    session.flush()
    run.rights_policy_id = rights.id
    rights.derived_storage_allowed = RightsDecision.ALLOWED
    connection.rights_policy_id = rights.id
    session.flush()
    summary = run_evidence(session, run)["rights_summary"]
    assert summary["raw_storage"] == "ALLOWED" and summary["derived_analysis"] == "UNKNOWN"
    monkeypatch.setattr(
        runtime, "readiness", lambda *args: {"runnable": True, "worker_verified": True}
    )
    assert (
        service.control.detail(tenant.id, site.id, "dataforseo")["operational_health"] == "HEALTHY"
    )
    queries = SystemQueries(session)
    assert (
        queries.runs(
            tenant.id,
            site.id,
            page=1,
            limit=25,
            provider_key="dataforseo",
            outcome="RECOVERED",
            timeliness="RECOVERED_LATE",
        )["total"]
        == 1
    )
    assert queries.runs(tenant.id, site.id, page=1, limit=25, provider_key="ga4")["total"] == 0
    obligation.status = ObligationStatus.FAILED
    obligation.satisfied_at = None
    session.flush()
    assert (
        service.control.detail(tenant.id, site.id, "dataforseo")["operational_health"]
        == "ATTENTION_REQUIRED"
    )


def test_multiple_targets_create_distinct_activity_not_attempt_rows(session: Session):
    from gis.models import TrackedQuery

    tenant, site, query, config, service = setup(session)
    second = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text="funding fee",
        normalized_query="funding fee",
    )
    session.add(second)
    session.flush()
    config.capabilities[0].target_ids = [query.id, second.id]
    config.activate = True
    service.save(tenant.id, site.id, "dataforseo", config)
    now = datetime.now(timezone.utc)
    schedule = session.scalar(
        select(ScheduleDefinition).where(ScheduleDefinition.tenant_id == tenant.id)
    )
    schedule.next_scheduled_at = now
    runs = Orchestrator(session).enqueue_due(now)
    assert len(runs) == 2 and len({r.obligation_id for r in runs}) == 2
    activity = provider_operations(
        session, config.policy.data_source_connection_id, tenant.id, site.id
    )["activity"]
    assert {a["target_display_name"] for a in activity} == {"va loan calculator", "funding fee"}


def test_provider_cost_lexeme_survives_json_decode_without_paid_call():
    import requests

    from gis.integrations.serp.dataforseo import DataForSEOProvider
    from gis.models import TrackedQuery

    response = requests.Response()
    response.status_code = 200
    response._content = b'{"status_code":20000,"tasks":[{"id":"fixture","status_code":20000,"cost":0.018000000000000001,"result":[]}]}'

    class Stub:
        def post(self, *args, **kwargs):
            return response

    query = TrackedQuery(
        query_text="fixture",
        language_code="en",
        device="desktop",
        country_code="US",
        requested_depth=100,
    )
    result = DataForSEOProvider("fixture", "fixture", session=Stub()).collect(query)
    assert result["tasks"][0]["cost"] == "0.018000000000000001"
