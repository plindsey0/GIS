from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from gis.models import (
    AlertStatus,
    ConnectionType,
    CostBudget,
    CostLedgerEntry,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    DependencyPolicy,
    ExecutionAttempt,
    FreshnessState,
    OperationalAlert,
    OrchestrationRun,
    OrchestrationStatus,
    PipelineDefinition,
    RightsDecision,
    ScheduleDefinition,
    ScheduleStatus,
    Site,
    Tenant,
    TriggerType,
)
from gis.orchestration.cli import json_default
from gis.orchestration.schedule import ScheduleExpressionError, next_occurrence
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.orchestration.service import (
    Orchestrator,
    PipelineResult,
    Worker,
    evaluate_budget,
    mark_stale,
    open_alert,
    resolve_alert,
)
from gis.seed import seed

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)


def scope(
    session: Session, *, paid: bool = False, cost: str = "0"
) -> tuple[Tenant, Site, PipelineDefinition]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    pipeline = PipelineDefinition(
        key=f"fixture-{uuid.uuid4()}",
        name="Fixture pipeline",
        handler_key="FIXTURE",
        paid_provider=paid,
        default_estimated_cost=Decimal(cost),
    )
    session.add(pipeline)
    session.commit()
    return tenant, site, pipeline


def schedule(
    session: Session,
    tenant: Tenant,
    site: Site,
    pipeline: PipelineDefinition,
    *,
    occurrence: datetime = NOW,
    max_attempts: int = 3,
) -> ScheduleDefinition:
    item = ScheduleDefinition(
        tenant_id=tenant.id,
        organization_id=site.organization_id,
        site_id=site.id,
        pipeline_id=pipeline.id,
        name=f"fixture-{uuid.uuid4()}",
        cron_expression="0 12 * * *",
        timezone="UTC",
        status=ScheduleStatus.ENABLED,
        next_scheduled_at=occurrence,
        max_attempts=max_attempts,
        retry_delay_seconds=10,
        freshness_sla_seconds=60,
    )
    session.add(item)
    session.commit()
    return item


def test_schedule_calculation_is_deterministic_and_timezone_aware() -> None:
    after = datetime(2026, 3, 7, 13, tzinfo=timezone.utc)
    result = next_occurrence("30 9 * * *", "America/New_York", after)
    assert result == datetime(2026, 3, 7, 14, 30, tzinfo=timezone.utc)
    spring = next_occurrence(
        "30 2 * * *", "America/New_York", datetime(2026, 3, 8, 5, tzinfo=timezone.utc)
    )
    assert spring.astimezone(ZoneInfo("America/New_York")).date() == date(2026, 3, 9)
    with pytest.raises(ScheduleExpressionError):
        next_occurrence("bad", "UTC", after)


def test_duplicate_schedule_occurrence_is_prevented(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    item = schedule(session, tenant, site, pipeline)
    first = Orchestrator(session).enqueue_due(NOW)
    assert len(first) == 1
    duplicate = OrchestrationRun(
        tenant_id=tenant.id,
        site_id=site.id,
        pipeline_id=pipeline.id,
        schedule_id=item.id,
        trigger_type=TriggerType.SCHEDULED,
        status=OrchestrationStatus.PENDING,
        scheduled_for=NOW,
        available_at=NOW,
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        session.flush()


def test_dependency_cycle_rejected(session: Session) -> None:
    tenant, site, first = scope(session)
    second = PipelineDefinition(key=f"second-{uuid.uuid4()}", name="Second", handler_key="FIXTURE")
    session.add(second)
    session.commit()
    manager = Orchestrator(session)
    manager.add_dependency(tenant.id, first.id, second.id, DependencyPolicy.ALL_SUCCESS, site.id)
    with pytest.raises(ValueError, match="cycle"):
        manager.add_dependency(
            tenant.id, second.id, first.id, DependencyPolicy.ALL_SUCCESS, site.id
        )


@pytest.mark.parametrize(
    ("policy", "upstream_status", "expected"),
    [
        (
            DependencyPolicy.ALL_SUCCESS,
            OrchestrationStatus.SUCCEEDED,
            OrchestrationStatus.SUCCEEDED,
        ),
        (DependencyPolicy.ALL_SUCCESS, OrchestrationStatus.FAILED, OrchestrationStatus.BLOCKED),
        (
            DependencyPolicy.ANY_SUCCESS,
            OrchestrationStatus.SUCCEEDED,
            OrchestrationStatus.SUCCEEDED,
        ),
        (DependencyPolicy.ANY_SUCCESS, OrchestrationStatus.FAILED, OrchestrationStatus.BLOCKED),
        (DependencyPolicy.ALWAYS, OrchestrationStatus.FAILED, OrchestrationStatus.SUCCEEDED),
    ],
)
def test_dependency_policies(
    session: Session,
    policy: DependencyPolicy,
    upstream_status: OrchestrationStatus,
    expected: OrchestrationStatus,
) -> None:
    tenant, site, upstream_pipeline = scope(session)
    downstream = PipelineDefinition(key=f"down-{uuid.uuid4()}", name="Down", handler_key="FIXTURE")
    session.add(downstream)
    session.commit()
    Orchestrator(session).add_dependency(
        tenant.id, upstream_pipeline.id, downstream.id, policy, site.id
    )
    upstream = OrchestrationRun(
        tenant_id=tenant.id,
        site_id=site.id,
        pipeline_id=upstream_pipeline.id,
        trigger_type=TriggerType.SCHEDULED,
        status=upstream_status,
        scheduled_for=NOW,
        available_at=NOW,
    )
    candidate = OrchestrationRun(
        tenant_id=tenant.id,
        site_id=site.id,
        pipeline_id=downstream.id,
        trigger_type=TriggerType.SCHEDULED,
        status=OrchestrationStatus.PENDING,
        scheduled_for=NOW + timedelta(hours=1),
        available_at=NOW,
    )
    session.add_all([upstream, candidate])
    session.commit()
    result = Worker(session, {"FIXTURE": lambda _session, _run: PipelineResult()}, "test").run_once(
        NOW
    )
    assert result and result.status is expected


def test_success_retry_history_max_attempt_and_worker_idempotency(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    item = schedule(session, tenant, site, pipeline, max_attempts=2)
    execution = Orchestrator(session).enqueue_due(NOW)[0]
    calls = 0

    def flaky(_session: Session, _run: OrchestrationRun) -> PipelineResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return PipelineResult(actual_cost=Decimal("0.25"))

    worker = Worker(session, {"FIXTURE": flaky}, "worker-a")
    first = worker.run_once(NOW)
    assert first and first.status is OrchestrationStatus.RETRY_WAIT
    second = worker.run_once(NOW + timedelta(seconds=10))
    assert second and second.status is OrchestrationStatus.SUCCEEDED
    attempts = session.scalars(
        select(ExecutionAttempt)
        .where(ExecutionAttempt.orchestration_run_id == execution.id)
        .order_by(ExecutionAttempt.attempt_number)
    ).all()
    assert [attempt.status for attempt in attempts] == [
        OrchestrationStatus.FAILED,
        OrchestrationStatus.SUCCEEDED,
    ]
    assert attempts[1].trigger_type is TriggerType.RETRY
    assert worker.run_once(NOW + timedelta(seconds=20)) is None
    state = session.scalar(select(FreshnessState).where(FreshnessState.schedule_id == item.id))
    assert state and state.last_successful_at and state.consecutive_failures == 0


def test_terminal_failure_alert_deduplication_and_resolution(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    schedule(session, tenant, site, pipeline, max_attempts=1)
    Orchestrator(session).enqueue_due(NOW)
    worker = Worker(
        session, {"FIXTURE": lambda _s, _r: (_ for _ in ()).throw(RuntimeError("boom"))}, "test"
    )
    result = worker.run_once(NOW)
    assert result and result.status is OrchestrationStatus.FAILED
    alert = session.scalar(select(OperationalAlert))
    assert alert and alert.status is AlertStatus.OPEN
    open_alert(session, result, "PIPELINE_FAILURE", "ERROR", "again", NOW + timedelta(minutes=1))
    session.commit()
    assert session.scalar(select(func.count()).select_from(OperationalAlert)) == 1
    assert alert.occurrence_count == 2
    assert resolve_alert(session, tenant.id, alert.deduplication_key, NOW)
    session.commit()
    assert alert.status is AlertStatus.RESOLVED


def test_bounded_backfill_and_tenant_connection_isolation(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    manager = Orchestrator(session)
    run = manager.request_run(
        tenant.id,
        pipeline.id,
        site_id=site.id,
        backfill_start=date(2026, 1, 1),
        backfill_end=date(2026, 1, 31),
    )
    assert run.trigger_type is TriggerType.BACKFILL
    with pytest.raises(ValueError):
        manager.request_run(
            tenant.id, pipeline.id, backfill_start=date(2024, 1, 1), backfill_end=date(2026, 1, 1)
        )
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4()}")
    session.add(other)
    session.commit()
    connection = DataSourceConnection(
        tenant_id=other.id,
        data_source_id=session.scalar(select(DataSource.id).limit(1)),
        connection_type=ConnectionType.NATIVE,
    )
    session.add(connection)
    session.commit()
    with pytest.raises(ValueError, match="outside"):
        manager.request_run(tenant.id, pipeline.id, site_id=site.id, connection_id=connection.id)


def test_budget_allow_block_and_actual_cost_accounting(session: Session) -> None:
    tenant, site, pipeline = scope(session, paid=True, cost="2")
    session.add(
        CostBudget(
            tenant_id=tenant.id,
            site_id=site.id,
            pipeline_id=pipeline.id,
            daily_limit=Decimal("3"),
            monthly_limit=Decimal("10"),
            per_run_limit=Decimal("2"),
        )
    )
    session.commit()
    run = Orchestrator(session).request_run(tenant.id, pipeline.id, site_id=site.id)
    assert evaluate_budget(session, run, NOW)[0].value == "ALLOW"
    Worker(
        session, {"FIXTURE": lambda _s, _r: PipelineResult(actual_cost=Decimal("2"))}, "test"
    ).run_once(NOW + timedelta(days=1))
    ledger = session.scalar(select(CostLedgerEntry))
    assert ledger and ledger.amount == Decimal("2")
    second = Orchestrator(session).request_run(tenant.id, pipeline.id, site_id=site.id)
    result = Worker(session, {"FIXTURE": lambda _s, _r: PipelineResult()}, "test").run_once(
        NOW + timedelta(days=1)
    )
    assert result and result.id == second.id and result.status is OrchestrationStatus.BLOCKED


def test_rights_unknown_propagates_without_handler_call(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    source = session.scalar(select(DataSource).where(DataSource.key == "manual"))
    assert source
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Unknown orchestration rights",
        derived_storage_allowed=RightsDecision.UNKNOWN,
    )
    session.add(policy)
    session.flush()
    connection = DataSourceConnection(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_id=source.id,
        rights_policy_id=policy.id,
        connection_type=ConnectionType.NATIVE,
    )
    session.add(connection)
    session.commit()
    run = Orchestrator(session).request_run(
        tenant.id, pipeline.id, site_id=site.id, connection_id=connection.id
    )
    called = False

    def handler(_session: Session, _run: OrchestrationRun) -> PipelineResult:
        nonlocal called
        called = True
        return PipelineResult()

    result = Worker(session, {"FIXTURE": handler}, "test").run_once(NOW + timedelta(days=1))
    assert result and result.id == run.id and result.error_classification == "RIGHTS_BLOCK"
    assert called is False


def test_freshness_stale_detection_uses_successful_execution(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    item = schedule(session, tenant, site, pipeline)
    state = FreshnessState(
        tenant_id=tenant.id,
        site_id=site.id,
        pipeline_id=pipeline.id,
        schedule_id=item.id,
        last_attempted_at=NOW,
        last_successful_at=NOW,
        freshness_sla_seconds=60,
    )
    session.add(state)
    session.commit()
    stale = mark_stale(session, NOW + timedelta(seconds=61))
    assert stale == [state] and state.stale_since == NOW + timedelta(seconds=60)
    assert session.scalar(
        select(OperationalAlert).where(OperationalAlert.alert_type == "STALE_SOURCE")
    )


def test_json_serialization_handles_domain_types() -> None:
    payload = {
        "id": uuid.uuid4(),
        "at": NOW,
        "amount": Decimal("1.25"),
        "status": OrchestrationStatus.PENDING,
    }
    restored = json.loads(json.dumps(payload, default=json_default))
    assert restored["at"].startswith("2026-08-30") and restored["amount"] == "1.25"


def test_vahomemath_cadence_seed_is_idempotent_and_inactive(session: Session) -> None:
    scope(session)
    first = seed_vahomemath_cadence(session)
    second = seed_vahomemath_cadence(session)
    assert len(first) == len(second) == 11
    assert {item.id for item in first} == {item.id for item in second}
    assert all(item.status is ScheduleStatus.DISABLED for item in second)


def test_worker_restart_recovers_abandoned_attempt(session: Session) -> None:
    tenant, site, pipeline = scope(session)
    run = Orchestrator(session).request_run(
        tenant.id,
        pipeline.id,
        site_id=site.id,
        configuration={"max_attempts": 2, "retry_delay_seconds": 10},
    )
    run.status = OrchestrationStatus.RUNNING
    attempt = ExecutionAttempt(
        orchestration_run_id=run.id,
        trigger_type=TriggerType.MANUAL,
        attempt_number=1,
        status=OrchestrationStatus.RUNNING,
        worker_id="lost-worker",
        started_at=NOW - timedelta(hours=2),
    )
    session.add(attempt)
    session.commit()
    recovered = Worker(
        session, {"FIXTURE": lambda _s, _r: PipelineResult()}, "new"
    ).recover_abandoned(NOW)
    assert recovered == [run]
    assert run.status is OrchestrationStatus.RETRY_WAIT
    assert attempt.status is OrchestrationStatus.FAILED
    assert attempt.error_classification == "WORKER_LOST"
