from __future__ import annotations

import argparse
import enum
import json
import socket
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.db import session_factory
from gis.models import (
    AlertStatus,
    CostBudget,
    CostLedgerEntry,
    ExecutionAttempt,
    ExecutorHeartbeat,
    ExecutorRole,
    FreshnessState,
    ObligationStatus,
    OperationalAlert,
    OrchestrationObligation,
    OrchestrationRun,
    PipelineDefinition,
    ScheduleDefinition,
    ScheduleStatus,
    Site,
    Tenant,
    TriggerType,
)
from gis.orchestration.execution import default_handlers
from gis.orchestration.schedule import next_occurrence, validate_cron
from gis.orchestration.seed import seed_vahomemath_cadence
from gis.orchestration.service import (
    Orchestrator,
    Worker,
    mark_stale,
    record_heartbeat,
    resolve_alert,
)


def json_default(value: object) -> object:
    if isinstance(value, (uuid.UUID, datetime, date, Decimal)):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def emit(value: object) -> None:
    print(json.dumps(value, default=json_default, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="gis-orchestrator")
    commands = root.add_subparsers(dest="command", required=True)
    schedule = commands.add_parser("schedule")
    schedule.add_argument("--tenant", required=True)
    schedule.add_argument("--pipeline", required=True)
    schedule.add_argument("--name", required=True)
    schedule.add_argument("--cron", required=True)
    schedule.add_argument("--timezone", default="UTC")
    schedule.add_argument("--site", type=uuid.UUID)
    schedule.add_argument("--connection", type=uuid.UUID)
    schedule.add_argument("--enable", action="store_true")
    schedule.add_argument("--freshness-sla-seconds", type=int)
    listing = commands.add_parser("list")
    listing.add_argument("--tenant", required=True)
    listing.add_argument("--site", type=uuid.UUID)
    for name in ("enable", "disable"):
        command = commands.add_parser(name)
        command.add_argument("--tenant", required=True)
        command.add_argument("--schedule", type=uuid.UUID, required=True)
    run = commands.add_parser("run")
    run.add_argument("--tenant", required=True)
    run.add_argument("--pipeline", required=True)
    run.add_argument("--site", type=uuid.UUID)
    run.add_argument("--connection", type=uuid.UUID)
    run.add_argument("--configuration-json", default="{}")
    backfill = commands.add_parser("backfill")
    backfill.add_argument("--tenant", required=True)
    backfill.add_argument("--pipeline", required=True)
    backfill.add_argument("--site", type=uuid.UUID)
    backfill.add_argument("--connection", type=uuid.UUID)
    backfill.add_argument("--start-date", type=date.fromisoformat, required=True)
    backfill.add_argument("--end-date", type=date.fromisoformat, required=True)
    backfill.add_argument("--configuration-json", default="{}")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--tenant", required=True)
    reconcile.add_argument("--pipeline", required=True)
    reconcile.add_argument("--site", type=uuid.UUID)
    reconcile.add_argument("--connection", type=uuid.UUID)
    reconcile.add_argument("--start-date", type=date.fromisoformat, required=True)
    reconcile.add_argument("--end-date", type=date.fromisoformat, required=True)
    reconcile.add_argument("--configuration-json", default="{}")
    for name in ("status", "history"):
        command = commands.add_parser(name)
        command.add_argument("--tenant", required=True)
        command.add_argument("--limit", type=int, default=50)
    retry = commands.add_parser("retry")
    retry.add_argument("--tenant", required=True)
    retry.add_argument("--execution", type=uuid.UUID, required=True)
    retry.add_argument("--confirm-provider-recovery", action="store_true")
    worker = commands.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--sleep-seconds", type=float, default=15)
    worker.add_argument("--worker-id", default=socket.gethostname())
    budget = commands.add_parser("budget")
    budget.add_argument("--tenant", required=True)
    budget.add_argument("--site", type=uuid.UUID)
    budget.add_argument("--pipeline")
    budget.add_argument("--daily", type=Decimal)
    budget.add_argument("--monthly", type=Decimal)
    budget.add_argument("--per-run", type=Decimal)
    alerts = commands.add_parser("alerts")
    alerts.add_argument("--tenant", required=True)
    alerts.add_argument("--resolve", type=uuid.UUID)
    cadence = commands.add_parser("seed-vahomemath")
    cadence.add_argument("--confirm-disabled", action="store_true", required=True)
    obligations = commands.add_parser("obligations")
    obligations.add_argument("--tenant", required=True)
    obligations.add_argument("--site", type=uuid.UUID)
    obligations.add_argument("--overdue", action="store_true")
    obligations.add_argument("--id", type=uuid.UUID)
    obligations.add_argument("--limit", type=int, default=100)
    catchup = commands.add_parser("catch-up")
    catchup.add_argument("--tenant", required=True)
    commands.add_parser("liveness")
    return root


def _tenant(session: Session, slug: str) -> Tenant:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if not tenant:
        raise ValueError("tenant not found")
    return tenant


def _pipeline(session: Session, key: str) -> PipelineDefinition:
    pipeline = session.scalar(select(PipelineDefinition).where(PipelineDefinition.key == key))
    if not pipeline:
        raise ValueError("pipeline not found")
    return pipeline


def _assert_site_scope(session: Session, tenant: Tenant, site_id: uuid.UUID | None) -> None:
    if site_id is None:
        return
    site = session.get(Site, site_id)
    if not site or site.tenant_id != tenant.id:
        raise ValueError("site is outside tenant scope")


def _run_json(run: OrchestrationRun) -> dict[str, object]:
    return {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "site_id": run.site_id,
        "pipeline_id": run.pipeline_id,
        "schedule_id": run.schedule_id,
        "trigger_type": run.trigger_type,
        "status": run.status,
        "scheduled_for": run.scheduled_for,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "estimated_provider_cost": run.estimated_provider_cost,
        "actual_provider_cost": run.actual_provider_cost,
        "currency": run.currency,
        "error_classification": run.error_classification,
        "error_detail": run.error_detail,
    }


def run(arguments: list[str] | None = None) -> int:
    args = _parser().parse_args(arguments)
    try:
        with session_factory()() as session:
            orchestrator = Orchestrator(session)
            if args.command == "worker":
                worker = Worker(session, default_handlers(), args.worker_id)
                while True:
                    record_heartbeat(
                        session,
                        args.worker_id,
                        ExecutorRole.SCHEDULER,
                        datetime.now(timezone.utc),
                        max(60, int(args.sleep_seconds * 4)),
                    )
                    worker.recover_abandoned()
                    orchestrator.enqueue_due()
                    mark_stale(session)
                    execution = worker.run_once()
                    if args.once:
                        emit(_run_json(execution) if execution else {"status": "IDLE"})
                        return 0
                    if not execution:
                        time.sleep(args.sleep_seconds)
            if args.command == "liveness":
                now = datetime.now(timezone.utc)
                emit(
                    [
                        {
                            "executor_id": item.executor_id,
                            "role": item.role,
                            "last_heartbeat_at": item.last_heartbeat_at,
                            "lease_expires_at": item.lease_expires_at,
                            "alive": item.lease_expires_at >= now,
                        }
                        for item in session.scalars(select(ExecutorHeartbeat)).all()
                    ]
                )
                return 0
            if args.command == "seed-vahomemath":
                schedules = seed_vahomemath_cadence(session)
                emit({"schedule_ids": [item.id for item in schedules], "activated": False})
                return 0
            tenant = _tenant(session, args.tenant)
            if args.command == "catch-up":
                created = orchestrator.enqueue_due()
                emit({"created": len(created), "run_ids": [item.id for item in created]})
                return 0
            if args.command == "obligations":
                obligation_statement = select(OrchestrationObligation).where(
                    OrchestrationObligation.tenant_id == tenant.id
                )
                if args.site:
                    obligation_statement = obligation_statement.where(
                        OrchestrationObligation.site_id == args.site
                    )
                if args.id:
                    obligation_statement = obligation_statement.where(
                        OrchestrationObligation.id == args.id
                    )
                if args.overdue:
                    obligation_statement = obligation_statement.where(
                        OrchestrationObligation.due_at < datetime.now(timezone.utc),
                        OrchestrationObligation.status.notin_(
                            [
                                ObligationStatus.SATISFIED,
                                ObligationStatus.EXPIRED,
                            ]
                        ),
                    )
                rows = session.scalars(
                    obligation_statement.order_by(OrchestrationObligation.due_at.desc()).limit(
                        args.limit
                    )
                ).all()
                now = datetime.now(timezone.utc)
                payload = []
                for item in rows:
                    linked_run = session.scalar(
                        select(OrchestrationRun)
                        .where(OrchestrationRun.obligation_id == item.id)
                        .order_by(OrchestrationRun.requested_at.desc())
                        .limit(1)
                    )
                    pipeline = session.get(PipelineDefinition, item.pipeline_id)
                    schedule = session.get(ScheduleDefinition, item.schedule_id)
                    attempt_triggers = (
                        list(
                            session.scalars(
                                select(ExecutionAttempt.trigger_type)
                                .where(ExecutionAttempt.orchestration_run_id == linked_run.id)
                                .order_by(ExecutionAttempt.attempt_number)
                            )
                        )
                        if linked_run
                        else []
                    )
                    completion = item.satisfied_at
                    timeliness = (
                        "ON_TIME"
                        if completion and completion <= item.due_at
                        else "RECOVERED_LATE"
                        if item.status is ObligationStatus.SATISFIED
                        else "MISSED_UNSATISFIED"
                        if item.due_at < now
                        else "NOT_YET_DUE"
                    )
                    payload.append(
                        {
                            "id": item.id,
                            "pipeline": pipeline.key if pipeline else None,
                            "schedule": schedule.name if schedule else None,
                            "window_start": item.window_start,
                            "window_end": item.window_end,
                            "due_at": item.due_at,
                            "created_at": item.created_at,
                            "completed_at": completion,
                            "lateness_seconds": max(
                                0.0, ((completion or now) - item.due_at).total_seconds()
                            ),
                            "timeliness": timeliness,
                            "status": item.status,
                            "completion_outcome": item.completion_outcome,
                            "attempt_count": item.attempt_count,
                            "next_attempt_at": item.next_attempt_at,
                            "failure_category": item.failure_category,
                            "readiness": linked_run.readiness_state if linked_run else None,
                            "trigger": linked_run.trigger_type if linked_run else None,
                            "attempt_triggers": attempt_triggers,
                            "orchestration_run_id": linked_run.id if linked_run else None,
                            "ingestion_run_id": item.ingestion_run_id,
                            "reason": item.status_reason,
                        }
                    )
                emit(payload)
                return 0
            if args.command == "schedule":
                pipeline = _pipeline(session, args.pipeline)
                _assert_site_scope(session, tenant, args.site)
                validate_cron(args.cron)
                schedule = ScheduleDefinition(
                    tenant_id=tenant.id,
                    site_id=args.site,
                    pipeline_id=pipeline.id,
                    data_source_connection_id=args.connection,
                    name=args.name,
                    cron_expression=args.cron,
                    timezone=args.timezone,
                    status=ScheduleStatus.ENABLED if args.enable else ScheduleStatus.DISABLED,
                    freshness_sla_seconds=args.freshness_sla_seconds,
                )
                schedule.next_scheduled_at = next_occurrence(
                    args.cron, args.timezone, datetime.now(timezone.utc)
                )
                session.add(schedule)
                session.commit()
                emit(
                    {
                        "schedule_id": schedule.id,
                        "status": schedule.status,
                        "next_run": schedule.next_scheduled_at,
                    }
                )
            elif args.command == "list":
                statement = select(ScheduleDefinition).where(
                    ScheduleDefinition.tenant_id == tenant.id
                )
                if args.site:
                    statement = statement.where(ScheduleDefinition.site_id == args.site)
                schedules_list = session.scalars(statement.order_by(ScheduleDefinition.name)).all()
                emit(
                    [
                        {
                            "id": item.id,
                            "name": item.name,
                            "status": item.status,
                            "cron": item.cron_expression,
                            "timezone": item.timezone,
                            "next_run": item.next_scheduled_at,
                        }
                        for item in schedules_list
                    ]
                )
            elif args.command in {"enable", "disable"}:
                existing_schedule = session.get(ScheduleDefinition, args.schedule)
                if not existing_schedule or existing_schedule.tenant_id != tenant.id:
                    raise ValueError("schedule not found")
                existing_schedule.status = (
                    ScheduleStatus.ENABLED if args.command == "enable" else ScheduleStatus.DISABLED
                )
                if args.command == "enable":
                    existing_schedule.next_scheduled_at = next_occurrence(
                        existing_schedule.cron_expression,
                        existing_schedule.timezone,
                        datetime.now(timezone.utc),
                    )
                session.commit()
                emit({"schedule_id": existing_schedule.id, "status": existing_schedule.status})
            elif args.command in {"run", "backfill", "reconcile"}:
                pipeline = _pipeline(session, args.pipeline)
                _assert_site_scope(session, tenant, args.site)
                configuration = json.loads(args.configuration_json)
                execution = orchestrator.request_run(
                    tenant.id,
                    pipeline.id,
                    site_id=args.site,
                    connection_id=args.connection,
                    configuration=configuration,
                    backfill_start=args.start_date
                    if args.command in {"backfill", "reconcile"}
                    else None,
                    backfill_end=args.end_date
                    if args.command in {"backfill", "reconcile"}
                    else None,
                    trigger_type=(
                        TriggerType.RECONCILIATION if args.command == "reconcile" else None
                    ),
                )
                emit(_run_json(execution))
            elif args.command in {"status", "history"}:
                runs = session.scalars(
                    select(OrchestrationRun)
                    .where(OrchestrationRun.tenant_id == tenant.id)
                    .order_by(OrchestrationRun.requested_at.desc())
                    .limit(args.limit)
                ).all()
                states = (
                    session.scalars(
                        select(FreshnessState).where(FreshnessState.tenant_id == tenant.id)
                    ).all()
                    if args.command == "status"
                    else []
                )
                emit(
                    {
                        "executions": [_run_json(item) for item in runs],
                        "freshness": [
                            {
                                "pipeline_id": item.pipeline_id,
                                "last_successful": item.last_successful_at,
                                "expected_next": item.expected_next_execution_at,
                                "stale_since": item.stale_since,
                                "consecutive_failures": item.consecutive_failures,
                            }
                            for item in states
                        ],
                    }
                )
            elif args.command == "retry":
                execution = session.get(OrchestrationRun, args.execution)
                if (
                    execution
                    and execution.configuration_json.get("provider_capability_policy_id")
                    and not args.confirm_provider_recovery
                ):
                    raise ValueError(
                        "Provider recovery can consume credits; review in Workbench or explicitly pass --confirm-provider-recovery"
                    )
                emit(_run_json(orchestrator.retry(tenant.id, args.execution)))
            elif args.command == "budget":
                _assert_site_scope(session, tenant, args.site)
                budget_pipeline = _pipeline(session, args.pipeline) if args.pipeline else None
                budget = CostBudget(
                    tenant_id=tenant.id,
                    site_id=args.site,
                    pipeline_id=budget_pipeline.id if budget_pipeline else None,
                    daily_limit=args.daily,
                    monthly_limit=args.monthly,
                    per_run_limit=args.per_run,
                )
                session.add(budget)
                session.commit()
                spent = session.scalar(
                    select(func.coalesce(func.sum(CostLedgerEntry.amount), 0)).where(
                        CostLedgerEntry.tenant_id == tenant.id
                    )
                )
                emit(
                    {
                        "budget_id": budget.id,
                        "daily": budget.daily_limit,
                        "monthly": budget.monthly_limit,
                        "per_run": budget.per_run_limit,
                        "lifetime_actual": spent,
                        "currency": budget.currency,
                    }
                )
            else:
                if args.resolve:
                    alert = session.get(OperationalAlert, args.resolve)
                    if not alert or alert.tenant_id != tenant.id:
                        raise ValueError("alert not found")
                    resolve_alert(session, tenant.id, alert.deduplication_key)
                    session.commit()
                alerts = session.scalars(
                    select(OperationalAlert)
                    .where(
                        OperationalAlert.tenant_id == tenant.id,
                        OperationalAlert.status == AlertStatus.OPEN,
                    )
                    .order_by(OperationalAlert.opened_at.desc())
                ).all()
                emit(
                    [
                        {
                            "id": item.id,
                            "type": item.alert_type,
                            "severity": item.severity,
                            "message": item.message,
                            "count": item.occurrence_count,
                            "opened_at": item.opened_at,
                        }
                        for item in alerts
                    ]
                )
        return 0
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        emit({"error": str(error), "error_type": type(error).__name__})
        return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
