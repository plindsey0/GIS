from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.api.system import SystemQueries
from gis.models import (
    CompletionOutcome,
    ExecutorHeartbeat,
    ExecutorRole,
    FailureCategory,
    ObligationStatus,
    OrchestrationObligation,
    OrchestrationStatus,
    PipelineDefinition,
    ScheduleDefinition,
    ScheduleStatus,
    Site,
    Tenant,
    TriggerType,
)
from gis.orchestration.reliability import ClassifiedFailure
from gis.orchestration.service import Orchestrator, PipelineResult, Worker, record_heartbeat
from gis.seed import seed

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def reliability_scope(
    session: Session, *, paid: bool = False, next_due: datetime = NOW
) -> tuple[Tenant, Site, PipelineDefinition, ScheduleDefinition]:
    seed(session, hostname="reliability.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    pipeline = PipelineDefinition(
        key=f"reliability-{uuid.uuid4()}",
        name="Reliability fixture",
        handler_key="FIXTURE",
        paid_provider=paid,
    )
    session.add(pipeline)
    session.flush()
    schedule = ScheduleDefinition(
        tenant_id=tenant.id,
        organization_id=site.organization_id,
        site_id=site.id,
        pipeline_id=pipeline.id,
        name=f"Reliability {uuid.uuid4()}",
        cron_expression="0 12 * * *",
        timezone="UTC",
        status=ScheduleStatus.ENABLED,
        next_scheduled_at=next_due,
        automatic_catchup_seconds=172800,
        terminal_horizon_seconds=604800,
        retry_profile="PAID_BOUNDED" if paid else "LOCAL_DETERMINISTIC",
        max_attempts=6,
    )
    session.add(schedule)
    session.commit()
    return tenant, site, pipeline, schedule


def test_daily_obligation_and_run_are_created_exactly_once(session: Session) -> None:
    _, _, _, schedule = reliability_scope(session)
    manager = Orchestrator(session)
    first = manager.enqueue_due(NOW + timedelta(hours=1))
    second = manager.enqueue_due(NOW + timedelta(hours=1))
    assert len(first) == 1 and second == []
    obligation = session.scalar(select(OrchestrationObligation))
    assert obligation and first[0].obligation_id == obligation.id
    assert first[0].trigger_type is TriggerType.CATCH_UP
    assert obligation.status is ObligationStatus.PENDING
    assert schedule.next_scheduled_at == NOW + timedelta(days=1)


def test_startup_catchup_is_bounded_and_disabled_schedule_creates_none(session: Session) -> None:
    _, _, _, schedule = reliability_scope(session, next_due=NOW - timedelta(days=30))
    created = Orchestrator(session).enqueue_due(NOW)
    assert 1 <= len(created) <= 3
    assert all(run.scheduled_for >= NOW - timedelta(days=2) for run in created if run.scheduled_for)
    schedule.status = ScheduleStatus.DISABLED
    schedule.next_scheduled_at = NOW
    session.commit()
    assert Orchestrator(session).enqueue_due(NOW + timedelta(hours=1)) == []


def test_transient_retry_satisfies_one_obligation(session: Session) -> None:
    _, _, _, _ = reliability_scope(session)
    run = Orchestrator(session).enqueue_due(NOW)[0]
    calls = 0

    def transient(_session: Session, _run: object) -> PipelineResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary network failure")
        return PipelineResult()

    worker = Worker(session, {"FIXTURE": transient}, "reliability-worker")
    first = worker.run_once(NOW)
    assert first and first.status is OrchestrationStatus.RETRY_WAIT
    second = worker.run_once(first.available_at)
    assert second and second.status is OrchestrationStatus.SUCCEEDED
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    assert obligation and obligation.status is ObligationStatus.SATISFIED
    assert obligation.attempt_count == 2
    assert session.scalar(select(func.count()).select_from(OrchestrationObligation)) == 1


def test_terminal_auth_failure_opens_manual_intervention_state(session: Session) -> None:
    _, _, _, _ = reliability_scope(session)
    run = Orchestrator(session).enqueue_due(NOW)[0]

    def denied(_session: Session, _run: object) -> PipelineResult:
        raise ClassifiedFailure(FailureCategory.AUTHENTICATION_FAILED, "credential rejected")

    result = Worker(session, {"FIXTURE": denied}, "reliability-worker").run_once(NOW)
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    assert result and result.status is OrchestrationStatus.FAILED
    assert obligation and obligation.status is ObligationStatus.BLOCKED
    assert obligation.failure_category is FailureCategory.AUTHENTICATION_FAILED
    assert obligation.next_attempt_at is None


def test_paid_retry_is_bounded_to_one_automatic_retry(session: Session) -> None:
    _, _, _, _ = reliability_scope(session, paid=True)
    run = Orchestrator(session).enqueue_due(NOW)[0]

    def throttled(_session: Session, _run: object) -> PipelineResult:
        raise ClassifiedFailure(
            FailureCategory.PROVIDER_429, "rate limited", retry_after_seconds=60
        )

    worker = Worker(session, {"FIXTURE": throttled}, "paid-fixture-worker")
    first = worker.run_once(NOW)
    assert first and first.status is OrchestrationStatus.RETRY_WAIT
    second = worker.run_once(first.available_at)
    assert second and second.status is OrchestrationStatus.FAILED
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    assert obligation and obligation.attempt_count == 2


def test_provider_pending_does_not_satisfy_obligation(session: Session) -> None:
    _, _, _, _ = reliability_scope(session)
    run = Orchestrator(session).enqueue_due(NOW)[0]
    result = Worker(
        session,
        {
            "FIXTURE": lambda _s, _r: PipelineResult(
                metadata={
                    "completion_outcome": "PROVIDER_DATA_PENDING",
                    "completion_reason": "reporting period remains revisable",
                }
            )
        },
        "pending-worker",
    ).run_once(NOW)
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    assert result and result.status is OrchestrationStatus.RETRY_WAIT
    assert obligation and obligation.status is ObligationStatus.PROVIDER_DATA_PENDING
    assert obligation.completion_outcome is CompletionOutcome.PROVIDER_DATA_PENDING


def test_executor_heartbeat_expires_explicitly(session: Session) -> None:
    heartbeat = record_heartbeat(session, "executor-a", ExecutorRole.SCHEDULER, NOW, 30)
    session.commit()
    assert heartbeat.lease_expires_at == NOW + timedelta(seconds=30)
    refreshed = record_heartbeat(
        session, "executor-a", ExecutorRole.SCHEDULER, NOW + timedelta(seconds=20), 30
    )
    session.commit()
    assert refreshed.id == heartbeat.id
    assert session.scalar(select(func.count()).select_from(ExecutorHeartbeat)) == 1


def test_recovered_late_is_currently_healthy_but_retained_in_history(session: Session) -> None:
    now = datetime.now(timezone.utc)
    tenant, site, pipeline, _ = reliability_scope(session, next_due=now - timedelta(hours=1))
    run = Orchestrator(session).enqueue_due(now)[0]
    completed = Worker(
        session, {"FIXTURE": lambda _session, _run: PipelineResult()}, "late-worker"
    ).run_once(now)
    record_heartbeat(session, "late-runtime", ExecutorRole.SCHEDULER, now, 3600)
    record_heartbeat(session, "late-runtime", ExecutorRole.WORKER, now, 3600)
    session.commit()

    assert completed and run.trigger_type is TriggerType.CATCH_UP
    summary = SystemQueries(session).pipeline_summary(pipeline, tenant.id, site.id)
    detail = SystemQueries(session).pipeline_detail(pipeline.key, tenant.id, site.id)
    assert summary["health"] == "HEALTHY"
    assert detail["latest_obligation"]["timeliness"] == "RECOVERED_LATE"
    assert detail["latest_obligation"]["lateness_seconds"] >= 3600
    assert detail["reliability"]["recovered_late_obligations"] == 1


def test_future_first_obligation_is_neutral_awaiting_state(session: Session) -> None:
    now = datetime.now(timezone.utc)
    tenant, site, pipeline, _ = reliability_scope(session, next_due=now + timedelta(days=1))
    record_heartbeat(session, "future-runtime", ExecutorRole.SCHEDULER, now, 3600)
    record_heartbeat(session, "future-runtime", ExecutorRole.WORKER, now, 3600)
    session.commit()

    payload = SystemQueries(session).pipelines(tenant.id, site.id)
    item = next(row for row in payload["items"] if row["key"] == pipeline.key)
    assert item["health"] == "AWAITING_FIRST_SCHEDULED_RUN"
    assert payload["health_counts"]["AWAITING_FIRST_SCHEDULED_RUN"] >= 1


def test_real_worker_completion_timestamp_follows_handler_work(session: Session) -> None:
    reliability_scope(session, next_due=datetime.now(timezone.utc) - timedelta(minutes=1))
    run = Orchestrator(session).enqueue_due()[0]
    handler_finished: datetime | None = None

    def handler(_session: Session, _run: object) -> PipelineResult:
        nonlocal handler_finished
        handler_finished = datetime.now(timezone.utc)
        return PipelineResult()

    completed = Worker(session, {"FIXTURE": handler}, "clock-worker").run_once()
    assert completed and completed.completed_at and handler_finished
    assert completed.completed_at >= handler_finished
    obligation = session.get(OrchestrationObligation, run.obligation_id)
    assert obligation and obligation.satisfied_at == completed.completed_at
