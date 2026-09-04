from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select, true
from sqlalchemy.orm import Session

from gis.models import (
    AlertStatus,
    BudgetDecision,
    CompletionOutcome,
    CostBudget,
    CostLedgerEntry,
    DataSourceConnection,
    DependencyPolicy,
    ExecutionAttempt,
    ExecutorHeartbeat,
    ExecutorRole,
    FailureCategory,
    FreshnessState,
    IngestionRun,
    ObligationStatus,
    OperationalAlert,
    OrchestrationObligation,
    OrchestrationRun,
    OrchestrationStatus,
    PermittedUse,
    PipelineDefinition,
    PipelineDependency,
    ReadinessState,
    RightsStatus,
    ScheduleDefinition,
    ScheduledTarget,
    ScheduleStatus,
    TriggerType,
)
from gis.orchestration.reliability import (
    classify_failure,
    completion_outcome,
    retry_at,
    retry_profile,
)
from gis.orchestration.schedule import next_occurrence
from gis.provenance.service import evaluate_connection_use


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PipelineResult:
    ingestion_run_id: uuid.UUID | None = None
    actual_cost: Decimal | None = Decimal("0")
    currency: str = "USD"
    metadata: dict[str, Any] | None = None


PipelineHandler = Callable[[Session, OrchestrationRun], PipelineResult]


class Orchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_dependency(
        self,
        tenant_id: uuid.UUID,
        upstream_pipeline_id: uuid.UUID,
        downstream_pipeline_id: uuid.UUID,
        policy: DependencyPolicy,
        site_id: uuid.UUID | None = None,
    ) -> PipelineDependency:
        if upstream_pipeline_id == downstream_pipeline_id:
            raise ValueError("pipeline cannot depend on itself")
        graph: dict[uuid.UUID, set[uuid.UUID]] = {}
        for dependency in self.session.scalars(
            select(PipelineDependency).where(PipelineDependency.tenant_id == tenant_id)
        ):
            graph.setdefault(dependency.upstream_pipeline_id, set()).add(
                dependency.downstream_pipeline_id
            )
        graph.setdefault(upstream_pipeline_id, set()).add(downstream_pipeline_id)

        def reaches(current: uuid.UUID, wanted: uuid.UUID, seen: set[uuid.UUID]) -> bool:
            if current == wanted:
                return True
            if current in seen:
                return False
            seen.add(current)
            return any(reaches(item, wanted, seen) for item in graph.get(current, set()))

        if reaches(downstream_pipeline_id, upstream_pipeline_id, set()):
            raise ValueError("pipeline dependency would create a cycle")
        dependency = PipelineDependency(
            tenant_id=tenant_id,
            site_id=site_id,
            upstream_pipeline_id=upstream_pipeline_id,
            downstream_pipeline_id=downstream_pipeline_id,
            policy=policy,
        )
        self.session.add(dependency)
        self.session.commit()
        return dependency

    def initialize_schedule(
        self, schedule: ScheduleDefinition, now: datetime | None = None
    ) -> None:
        schedule.next_scheduled_at = next_occurrence(
            schedule.cron_expression, schedule.timezone, now or utcnow()
        )

    def enqueue_due(self, now: datetime | None = None) -> list[OrchestrationRun]:
        current = now or utcnow()
        due = self.session.scalars(
            select(ScheduleDefinition)
            .where(
                ScheduleDefinition.status == ScheduleStatus.ENABLED,
                ScheduleDefinition.next_scheduled_at <= current,
            )
            .with_for_update(skip_locked=True)
        ).all()
        created: list[OrchestrationRun] = []
        for schedule in due:
            assert schedule.next_scheduled_at is not None
            lower_bound = current - timedelta(seconds=schedule.automatic_catchup_seconds)
            occurrence = schedule.next_scheduled_at
            if occurrence < lower_bound:
                occurrence = next_occurrence(
                    schedule.cron_expression,
                    schedule.timezone,
                    lower_bound - timedelta(minutes=1),
                )
            while occurrence <= current:
                created.extend(self._materialize_obligation(schedule, occurrence, current))
                occurrence = next_occurrence(
                    schedule.cron_expression, schedule.timezone, occurrence
                )
            schedule.next_scheduled_at = occurrence
        self.session.commit()
        return created

    def _materialize_obligation(
        self, schedule: ScheduleDefinition, occurrence: datetime, current: datetime
    ) -> list[OrchestrationRun]:
        targets = self.session.scalars(
            select(ScheduledTarget).where(
                ScheduledTarget.schedule_id == schedule.id, ScheduledTarget.active.is_(True)
            )
        ).all()
        selected_targets: list[ScheduledTarget | None] = list(targets) or [None]
        created: list[OrchestrationRun] = []
        window_seconds = int(
            schedule.configuration_json.get(
                "obligation_window_seconds",
                604800 if "weekly" in schedule.name.lower() else 86400,
            )
        )
        for target in selected_targets:
            target_id = target.id if target else None
            obligation = self.session.scalar(
                select(OrchestrationObligation).where(
                    OrchestrationObligation.schedule_id == schedule.id,
                    OrchestrationObligation.target_id.is_(None)
                    if target is None
                    else OrchestrationObligation.target_id == target.id,
                    OrchestrationObligation.window_start
                    == occurrence - timedelta(seconds=window_seconds),
                    OrchestrationObligation.window_end == occurrence,
                    OrchestrationObligation.policy_version == schedule.policy_version,
                )
            )
            if not obligation:
                obligation = OrchestrationObligation(
                    tenant_id=schedule.tenant_id,
                    site_id=schedule.site_id,
                    pipeline_id=schedule.pipeline_id,
                    schedule_id=schedule.id,
                    target_id=target_id,
                    data_source_connection_id=schedule.data_source_connection_id,
                    policy_version=schedule.policy_version,
                    window_start=occurrence - timedelta(seconds=window_seconds),
                    window_end=occurrence,
                    due_at=occurrence,
                    expires_at=occurrence + timedelta(seconds=schedule.terminal_horizon_seconds),
                    status=ObligationStatus.PENDING,
                    next_attempt_at=current,
                    metadata_json={"preferred_execution_at": occurrence.isoformat()},
                )
                self.session.add(obligation)
                self.session.flush()
            existing = self.session.scalar(
                select(OrchestrationRun).where(OrchestrationRun.obligation_id == obligation.id)
            )
            if existing:
                continue
            configured_estimate = schedule.configuration_json.get("estimated_provider_cost")
            run = OrchestrationRun(
                tenant_id=schedule.tenant_id,
                organization_id=schedule.organization_id,
                site_id=schedule.site_id,
                pipeline_id=schedule.pipeline_id,
                schedule_id=schedule.id,
                target_id=target_id,
                obligation_id=obligation.id,
                data_source_connection_id=schedule.data_source_connection_id,
                rights_policy_id=schedule.rights_policy_id,
                trigger_type=(
                    TriggerType.CATCH_UP
                    if current > occurrence + timedelta(minutes=1)
                    else TriggerType.SCHEDULED
                ),
                status=OrchestrationStatus.PENDING,
                scheduled_for=occurrence,
                available_at=current,
                estimated_provider_cost=(
                    Decimal(str(configured_estimate))
                    if configured_estimate is not None
                    else self._estimated_cost(schedule.pipeline_id)
                ),
                configuration_json={
                    **schedule.configuration_json,
                    **(target.configuration_json if target else {}),
                    **(
                        {"target_type": target.target_type, "target_key": target.target_key}
                        if target
                        else {}
                    ),
                    "obligation_window_start": obligation.window_start.isoformat(),
                    "obligation_window_end": obligation.window_end.isoformat(),
                },
            )
            self.session.add(run)
            self.session.flush()
            created.append(run)
        return created

    def request_run(
        self,
        tenant_id: uuid.UUID,
        pipeline_id: uuid.UUID,
        *,
        site_id: uuid.UUID | None = None,
        connection_id: uuid.UUID | None = None,
        configuration: dict[str, Any] | None = None,
        backfill_start: date | None = None,
        backfill_end: date | None = None,
        trigger_type: TriggerType | None = None,
    ) -> OrchestrationRun:
        if (backfill_start is None) != (backfill_end is None):
            raise ValueError("backfill start and end must be supplied together")
        if backfill_start and backfill_end and backfill_end < backfill_start:
            raise ValueError("backfill end must be on or after start")
        if backfill_start and backfill_end and (backfill_end - backfill_start).days > 366:
            raise ValueError("backfill range may not exceed 367 days")
        if connection_id:
            connection = self.session.get(DataSourceConnection, connection_id)
            if (
                not connection
                or connection.tenant_id != tenant_id
                or (site_id is not None and connection.site_id != site_id)
            ):
                raise ValueError("connection is outside the requested tenant/site scope")
        run = OrchestrationRun(
            tenant_id=tenant_id,
            site_id=site_id,
            pipeline_id=pipeline_id,
            data_source_connection_id=connection_id,
            trigger_type=trigger_type
            or (TriggerType.BACKFILL if backfill_start else TriggerType.MANUAL),
            status=OrchestrationStatus.PENDING,
            available_at=utcnow(),
            backfill_start=backfill_start,
            backfill_end=backfill_end,
            estimated_provider_cost=Decimal(
                str(
                    (configuration or {}).get(
                        "estimated_provider_cost", self._estimated_cost(pipeline_id)
                    )
                )
            ),
            configuration_json=configuration or {},
        )
        self.session.add(run)
        self.session.commit()
        return run

    def retry(self, tenant_id: uuid.UUID, run_id: uuid.UUID) -> OrchestrationRun:
        run = self.session.scalar(
            select(OrchestrationRun).where(OrchestrationRun.id == run_id).with_for_update()
        )
        if not run or run.tenant_id != tenant_id:
            raise ValueError("execution not found")
        if run.status not in {OrchestrationStatus.FAILED, OrchestrationStatus.BLOCKED}:
            raise ValueError("only failed or blocked executions can be retried")
        if run.configuration_json.get("provider_capability_policy_id"):
            from gis.provider_control.recovery import recovery_preview

            check = recovery_preview(self.session, run)
            if check["blockers"]:
                raise ValueError("; ".join(check["blockers"]))
        run.status = OrchestrationStatus.PENDING
        run.trigger_type = TriggerType.RETRY
        run.available_at = utcnow()
        run.completed_at = None
        run.error_classification = None
        run.error_detail = None
        run.completion_outcome = None
        if run.obligation_id:
            obligation = self.session.get(OrchestrationObligation, run.obligation_id)
            if obligation:
                obligation.status = ObligationStatus.PENDING
                obligation.next_attempt_at = run.available_at
                obligation.failure_category = None
                obligation.status_reason = "Operator requested a safe retry."
        self.session.commit()
        return run

    def _estimated_cost(self, pipeline_id: uuid.UUID) -> Decimal:
        pipeline = self.session.get(PipelineDefinition, pipeline_id)
        if not pipeline:
            raise ValueError("pipeline not found")
        return pipeline.default_estimated_cost


class Worker:
    def __init__(
        self, session: Session, handlers: dict[str, PipelineHandler], worker_id: str
    ) -> None:
        self.session = session
        self.handlers = handlers
        self.worker_id = worker_id

    def run_once(self, now: datetime | None = None) -> OrchestrationRun | None:
        current = now or utcnow()
        record_heartbeat(self.session, self.worker_id, ExecutorRole.WORKER, current)
        run = self.session.scalar(
            select(OrchestrationRun)
            .where(
                OrchestrationRun.status.in_(
                    [
                        OrchestrationStatus.PENDING,
                        OrchestrationStatus.RETRY_WAIT,
                        OrchestrationStatus.WAITING_DEPENDENCY,
                    ]
                ),
                OrchestrationRun.available_at <= current,
                OrchestrationRun.pipeline_id.not_in(
                    select(PipelineDefinition.id).where(PipelineDefinition.paid_provider.is_(True))
                )
                if os.environ.get("GIS_PAID_EXECUTION_DISABLED") == "1"
                else true(),
            )
            .order_by(OrchestrationRun.available_at, OrchestrationRun.requested_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not run:
            return None
        pipeline = self.session.get(PipelineDefinition, run.pipeline_id)
        if not pipeline or not pipeline.active:
            return self._block(
                run, "MALFORMED_CONFIGURATION", "pipeline is missing or inactive", current
            )
        dependency = self._dependency_decision(run)
        if dependency == "WAIT":
            run.status = OrchestrationStatus.WAITING_DEPENDENCY
            run.available_at = current + timedelta(seconds=60)
            self.session.commit()
            return run

        if dependency == "BLOCK":
            run.readiness_state = ReadinessState.BLOCKED
            run.readiness_detail = {"reason": "upstream dependency policy was not satisfied"}
            return self._block(
                run, "DEPENDENCY_FAILURE", "upstream dependency policy was not satisfied", current
            )
        stale_inputs = self._stale_inputs(run)
        run.readiness_state = (
            ReadinessState.READY_WITH_STALE_INPUT if stale_inputs else ReadinessState.READY
        )
        run.readiness_detail = {"stale_upstream_pipeline_ids": stale_inputs}
        if run.data_source_connection_id:
            connection = self.session.get(DataSourceConnection, run.data_source_connection_id)
            if not connection or connection.tenant_id != run.tenant_id:
                return self._block(
                    run, "TENANT_SCOPE", "source connection is outside tenant scope", current
                )
            evaluation = evaluate_connection_use(
                self.session, connection, PermittedUse.NORMALIZED_RETENTION
            )
            if evaluation.status is not RightsStatus.ALLOWED:
                run.rights_policy_id = evaluation.policy_id
                return self._block(run, "RIGHTS_BLOCK", str(evaluation.reason), current)
            run.rights_policy_id = evaluation.policy_id
        decision, reason = evaluate_budget(self.session, run, current)
        if decision is BudgetDecision.BLOCK:
            return self._block(run, "BUDGET_EXCEEDED", reason, current)
        attempt_count = (
            self.session.scalar(
                select(func.count())
                .select_from(ExecutionAttempt)
                .where(ExecutionAttempt.orchestration_run_id == run.id)
            )
            or 0
        )
        attempt = ExecutionAttempt(
            orchestration_run_id=run.id,
            trigger_type=TriggerType.RETRY if attempt_count else run.trigger_type,
            attempt_number=attempt_count + 1,
            status=OrchestrationStatus.RUNNING,
            worker_id=self.worker_id,
            started_at=current,
            heartbeat_at=current,
            lease_expires_at=current + timedelta(minutes=5),
            estimated_provider_cost=run.estimated_provider_cost,
        )
        run.status = OrchestrationStatus.RUNNING
        run.started_at = run.started_at or current
        obligation = (
            self.session.get(OrchestrationObligation, run.obligation_id)
            if run.obligation_id
            else None
        )
        if obligation:
            obligation.status = ObligationStatus.RUNNING
            obligation.attempt_count = attempt_count + 1
        self.session.add(attempt)
        self.session.commit()
        result = None
        try:
            handler = self.handlers[pipeline.handler_key]
            result = handler(self.session, run)
            if result.actual_cost is not None and result.actual_cost < 0:
                result = None
                raise ValueError("actual cost cannot be negative")
            if result.ingestion_run_id:
                from gis.orchestration.ingestion import ingestion_failure

                ingestion = self.session.get(IngestionRun, result.ingestion_run_id)
                if (
                    not ingestion
                    or ingestion.tenant_id != run.tenant_id
                    or ingestion.site_id != run.site_id
                    or ingestion.data_source_connection_id != run.data_source_connection_id
                ):
                    result = None
                    raise ValueError(
                        "Required ingestion linkage is missing or outside execution scope"
                    )
                failure = ingestion_failure(ingestion)
                if failure:
                    raise failure
            completed = now or utcnow()
            attempt.status = OrchestrationStatus.SUCCEEDED
            attempt.completed_at = completed
            attempt.ingestion_run_id = result.ingestion_run_id
            attempt.actual_provider_cost = result.actual_cost
            run.status = OrchestrationStatus.SUCCEEDED
            run.completed_at = completed
            run.ingestion_run_id = result.ingestion_run_id
            run.actual_provider_cost = result.actual_cost
            run.currency = result.currency
            run.error_classification = None
            run.error_detail = None
            outcome = completion_outcome(result.metadata)
            run.completion_outcome = outcome
            if obligation:
                obligation.ingestion_run_id = result.ingestion_run_id
                obligation.completion_outcome = outcome
                if outcome in {
                    CompletionOutcome.SUCCEEDED_COMPLETE,
                    CompletionOutcome.SUCCEEDED_NO_DATA_EXPECTED,
                }:
                    obligation.status = ObligationStatus.SATISFIED
                    obligation.satisfied_at = completed
                    obligation.next_attempt_at = None
                    obligation.status_reason = "Required data obligation satisfied."
                else:
                    profile = retry_profile(schedule_for(self.session, run), pipeline)
                    obligation.status = ObligationStatus.PROVIDER_DATA_PENDING
                    obligation.next_attempt_at = completed + timedelta(
                        seconds=profile.reconciliation_delay_seconds or 21600
                    )
                    obligation.status_reason = str(
                        (result.metadata or {}).get(
                            "completion_reason", "Provider data remains pending reconciliation."
                        )
                    )
                    run.status = OrchestrationStatus.RETRY_WAIT
                    run.available_at = obligation.next_attempt_at
            self._record_cost(run, pipeline, completed)
            self._update_freshness(
                run,
                outcome
                in {
                    CompletionOutcome.SUCCEEDED_COMPLETE,
                    CompletionOutcome.SUCCEEDED_NO_DATA_EXPECTED,
                },
                completed,
            )
            self.session.commit()
            return run

        except Exception as error:
            self.session.rollback()
            run = self.session.get(OrchestrationRun, run.id)
            refreshed_attempt = self.session.get(ExecutionAttempt, attempt.id)
            assert run and refreshed_attempt
            attempt = refreshed_attempt
            if result is not None:
                attempt.ingestion_run_id = result.ingestion_run_id
                run.ingestion_run_id = result.ingestion_run_id
                attempt.actual_provider_cost = result.actual_cost
                run.actual_provider_cost = result.actual_cost
                if obligation:
                    obligation.ingestion_run_id = result.ingestion_run_id
            completed = now or utcnow()
            attempt.status = OrchestrationStatus.FAILED
            attempt.completed_at = completed
            category, provider_retry_after = classify_failure(error)
            attempt.error_classification = type(error).__name__
            attempt.error_detail = str(error)
            attempt.failure_category = category
            run.error_classification = type(error).__name__
            run.error_detail = str(error)
            run.completion_outcome = CompletionOutcome.FAILED_RETRYABLE
            profile = retry_profile(schedule_for(self.session, run), pipeline)
            next_attempt = retry_at(
                profile, category, attempt.attempt_number, completed, provider_retry_after
            )
            schedule = schedule_for(self.session, run)
            configured_max_attempts = (
                schedule.max_attempts
                if schedule
                else int(run.configuration_json.get("max_attempts", len(profile.delays) + 1))
            )
            if attempt.attempt_number >= configured_max_attempts:
                next_attempt = None
            if schedule and completed >= (run.scheduled_for or completed) + timedelta(
                seconds=schedule.terminal_horizon_seconds
            ):
                next_attempt = None
            if next_attempt is not None:
                run.status = OrchestrationStatus.RETRY_WAIT
                run.available_at = next_attempt
                attempt.retry_after_at = next_attempt
                if obligation:
                    obligation.status = ObligationStatus.RETRY_WAIT
                    obligation.next_attempt_at = next_attempt
                    obligation.failure_category = category
                    obligation.status_reason = str(error)
            else:
                run.status = OrchestrationStatus.FAILED
                run.completed_at = completed
                run.completion_outcome = CompletionOutcome.FAILED_TERMINAL
                if obligation:
                    obligation.status = (
                        ObligationStatus.BLOCKED
                        if category
                        in {
                            FailureCategory.AUTHENTICATION_FAILED,
                            FailureCategory.AUTHORIZATION_FAILED,
                            FailureCategory.CONFIGURATION_ERROR,
                            FailureCategory.RIGHTS_BLOCKED,
                            FailureCategory.BUDGET_BLOCKED,
                        }
                        else ObligationStatus.FAILED
                    )
                    obligation.completion_outcome = CompletionOutcome.FAILED_TERMINAL
                    obligation.failure_category = category
                    obligation.next_attempt_at = None
                    obligation.status_reason = str(error)
                open_alert(self.session, run, "PIPELINE_FAILURE", "ERROR", str(error), completed)
            self._update_freshness(run, False, completed)
            self.session.commit()
            return run

    def recover_abandoned(
        self, now: datetime | None = None, stale_after_seconds: int = 3600
    ) -> list[OrchestrationRun]:
        current = now or utcnow()
        cutoff = current - timedelta(seconds=stale_after_seconds)
        attempts = self.session.scalars(
            select(ExecutionAttempt).where(
                ExecutionAttempt.status == OrchestrationStatus.RUNNING,
                or_(
                    ExecutionAttempt.lease_expires_at < current,
                    ExecutionAttempt.lease_expires_at.is_(None),
                ),
                ExecutionAttempt.started_at < cutoff,
            )
        ).all()
        recovered: list[OrchestrationRun] = []
        for attempt in attempts:
            run = self.session.get(OrchestrationRun, attempt.orchestration_run_id)
            if not run or run.status is not OrchestrationStatus.RUNNING:
                continue
            attempt.status = OrchestrationStatus.FAILED
            attempt.completed_at = current
            attempt.error_classification = "WORKER_LOST"
            attempt.error_detail = "worker attempt exceeded the recovery timeout"
            attempt.failure_category = FailureCategory.ABANDONED_EXECUTION
            run.completion_outcome = CompletionOutcome.ABANDONED
            max_attempts, delay, _ = self._retry_policy(run)
            run.error_classification = attempt.error_classification
            run.error_detail = attempt.error_detail
            obligation = (
                self.session.get(OrchestrationObligation, run.obligation_id)
                if run.obligation_id
                else None
            )
            if attempt.attempt_number < max_attempts:
                run.status = OrchestrationStatus.RETRY_WAIT
                run.available_at = current + timedelta(seconds=delay)
                if obligation:
                    obligation.status = ObligationStatus.RETRY_WAIT
                    obligation.next_attempt_at = run.available_at
                    obligation.failure_category = FailureCategory.ABANDONED_EXECUTION
            else:
                run.status = OrchestrationStatus.FAILED
                run.completed_at = current
                open_alert(
                    self.session,
                    run,
                    "PIPELINE_FAILURE",
                    "ERROR",
                    attempt.error_detail,
                    current,
                )
                if obligation:
                    obligation.status = ObligationStatus.FAILED
                    obligation.completion_outcome = CompletionOutcome.ABANDONED
                    obligation.failure_category = FailureCategory.ABANDONED_EXECUTION
            self._update_freshness(run, False, current)
            recovered.append(run)
        self.session.commit()
        return recovered

    def _dependency_decision(self, run: OrchestrationRun) -> str:
        dependencies = self.session.scalars(
            select(PipelineDependency).where(
                PipelineDependency.tenant_id == run.tenant_id,
                PipelineDependency.downstream_pipeline_id == run.pipeline_id,
                or_(
                    PipelineDependency.site_id.is_(None), PipelineDependency.site_id == run.site_id
                ),
            )
        ).all()
        if not dependencies or run.trigger_type in {
            TriggerType.MANUAL,
            TriggerType.BACKFILL,
            TriggerType.RETRY,
        }:
            return "RUN"
        if all(item.policy is DependencyPolicy.ALWAYS for item in dependencies):
            # ALWAYS means the downstream processor is allowed to run with whatever
            # upstream state is currently available, including an intentionally
            # disabled collector with no execution in the dependency window.
            return "RUN"
        statuses: list[OrchestrationStatus | None] = []
        dependency_window = timedelta(
            seconds=int(run.configuration_json.get("dependency_window_seconds", 604800))
        )
        dependency_reference = run.scheduled_for or run.requested_at
        for dependency in dependencies:
            upstream = self.session.scalar(
                select(OrchestrationRun.status)
                .where(
                    OrchestrationRun.tenant_id == run.tenant_id,
                    OrchestrationRun.pipeline_id == dependency.upstream_pipeline_id,
                    OrchestrationRun.scheduled_for <= dependency_reference,
                    OrchestrationRun.scheduled_for >= dependency_reference - dependency_window,
                )
                .order_by(OrchestrationRun.scheduled_for.desc(), OrchestrationRun.created_at.desc())
                .limit(1)
            )
            statuses.append(upstream)
        terminal = {
            OrchestrationStatus.SUCCEEDED,
            OrchestrationStatus.FAILED,
            OrchestrationStatus.BLOCKED,
            OrchestrationStatus.CANCELLED,
        }
        if any(status not in terminal for status in statuses):
            return "WAIT"
        policies = {item.policy for item in dependencies}
        if DependencyPolicy.ALWAYS in policies:
            return "RUN"
        successes = [status is OrchestrationStatus.SUCCEEDED for status in statuses]
        if DependencyPolicy.ALL_SUCCESS in policies and not all(successes):
            return "BLOCK"
        if DependencyPolicy.ANY_SUCCESS in policies and not any(successes):
            return "BLOCK"
        return "RUN"

    def _stale_inputs(self, run: OrchestrationRun) -> list[str]:
        upstream_ids = self.session.scalars(
            select(PipelineDependency.upstream_pipeline_id).where(
                PipelineDependency.tenant_id == run.tenant_id,
                PipelineDependency.downstream_pipeline_id == run.pipeline_id,
                or_(
                    PipelineDependency.site_id.is_(None),
                    PipelineDependency.site_id == run.site_id,
                ),
            )
        ).all()
        if not upstream_ids:
            return []
        return [
            str(item.pipeline_id)
            for item in self.session.scalars(
                select(FreshnessState).where(
                    FreshnessState.tenant_id == run.tenant_id,
                    FreshnessState.pipeline_id.in_(upstream_ids),
                    FreshnessState.stale_since.is_not(None),
                )
            ).all()
        ]

    def _retry_policy(self, run: OrchestrationRun) -> tuple[int, int, bool]:
        schedule = (
            self.session.get(ScheduleDefinition, run.schedule_id) if run.schedule_id else None
        )
        return (
            schedule.max_attempts
            if schedule
            else int(run.configuration_json.get("max_attempts", 3)),
            schedule.retry_delay_seconds
            if schedule
            else int(run.configuration_json.get("retry_delay_seconds", 300)),
            schedule.exponential_backoff
            if schedule
            else bool(run.configuration_json.get("exponential_backoff", True)),
        )

    def _block(
        self, run: OrchestrationRun, classification: str, detail: str, now: datetime
    ) -> OrchestrationRun:
        run.status = OrchestrationStatus.BLOCKED
        run.completed_at = now
        run.error_classification = classification
        run.error_detail = detail
        category = {
            "RIGHTS_BLOCK": FailureCategory.RIGHTS_BLOCKED,
            "BUDGET_EXCEEDED": FailureCategory.BUDGET_BLOCKED,
            "MALFORMED_CONFIGURATION": FailureCategory.CONFIGURATION_ERROR,
            "TENANT_SCOPE": FailureCategory.CONFIGURATION_ERROR,
        }.get(classification, FailureCategory.UNKNOWN_TERMINAL)
        run.completion_outcome = {
            FailureCategory.RIGHTS_BLOCKED: CompletionOutcome.BLOCKED_RIGHTS,
            FailureCategory.BUDGET_BLOCKED: CompletionOutcome.BLOCKED_BUDGET,
            FailureCategory.CONFIGURATION_ERROR: CompletionOutcome.BLOCKED_CONFIGURATION,
        }.get(category, CompletionOutcome.FAILED_TERMINAL)
        if run.obligation_id:
            obligation = self.session.get(OrchestrationObligation, run.obligation_id)
            if obligation:
                obligation.status = ObligationStatus.BLOCKED
                obligation.completion_outcome = run.completion_outcome
                obligation.failure_category = category
                obligation.status_reason = detail
                obligation.next_attempt_at = None
        open_alert(self.session, run, classification, "ERROR", detail, now)
        self._update_freshness(run, False, now)
        self.session.commit()
        return run

    def _update_freshness(self, run: OrchestrationRun, success: bool, now: datetime) -> None:
        state = self.session.scalar(
            select(FreshnessState).where(
                FreshnessState.tenant_id == run.tenant_id,
                FreshnessState.site_id.is_(run.site_id)
                if run.site_id is None
                else FreshnessState.site_id == run.site_id,
                FreshnessState.pipeline_id == run.pipeline_id,
                FreshnessState.schedule_id.is_(run.schedule_id)
                if run.schedule_id is None
                else FreshnessState.schedule_id == run.schedule_id,
            )
        )
        schedule = (
            self.session.get(ScheduleDefinition, run.schedule_id) if run.schedule_id else None
        )
        if not state:
            state = FreshnessState(
                tenant_id=run.tenant_id,
                site_id=run.site_id,
                pipeline_id=run.pipeline_id,
                schedule_id=run.schedule_id,
            )
            self.session.add(state)
        state.last_attempted_at = now
        state.expected_next_execution_at = schedule.next_scheduled_at if schedule else None
        state.freshness_sla_seconds = schedule.freshness_sla_seconds if schedule else None
        if success:
            state.last_successful_at = now
            state.consecutive_failures = 0
            state.stale_since = None
            resolve_alert(
                self.session,
                run.tenant_id,
                f"STALE_SOURCE:{run.schedule_id or run.pipeline_id}",
                now,
            )
        else:
            state.consecutive_failures = (state.consecutive_failures or 0) + 1

    def _record_cost(
        self, run: OrchestrationRun, pipeline: PipelineDefinition, now: datetime
    ) -> None:
        source_id = pipeline.data_source_id
        self.session.add(
            CostLedgerEntry(
                tenant_id=run.tenant_id,
                site_id=run.site_id,
                data_source_id=source_id,
                pipeline_id=run.pipeline_id,
                schedule_id=run.schedule_id,
                orchestration_run_id=run.id,
                amount=run.actual_provider_cost or Decimal("0"),
                currency=run.currency,
                occurred_at=now,
            )
        )


def schedule_for(session: Session, run: OrchestrationRun) -> ScheduleDefinition | None:
    return session.get(ScheduleDefinition, run.schedule_id) if run.schedule_id else None


def record_heartbeat(
    session: Session,
    executor_id: str,
    role: ExecutorRole,
    now: datetime | None = None,
    lease_seconds: int = 60,
) -> ExecutorHeartbeat:
    current = now or utcnow()
    heartbeat = session.scalar(
        select(ExecutorHeartbeat).where(
            ExecutorHeartbeat.executor_id == executor_id,
            ExecutorHeartbeat.role == role,
        )
    )
    if not heartbeat:
        heartbeat = ExecutorHeartbeat(
            executor_id=executor_id,
            role=role,
            started_at=current,
            last_heartbeat_at=current,
            lease_expires_at=current + timedelta(seconds=lease_seconds),
        )
        session.add(heartbeat)
    else:
        heartbeat.last_heartbeat_at = current
        heartbeat.lease_expires_at = current + timedelta(seconds=lease_seconds)
    from gis.provider_control.runtime import attest

    heartbeat.metadata_json = {**(heartbeat.metadata_json or {}), **attest(session)}
    session.flush()
    return heartbeat


def evaluate_budget(
    session: Session, run: OrchestrationRun, now: datetime
) -> tuple[BudgetDecision, str]:
    pipeline = session.get(PipelineDefinition, run.pipeline_id)
    source_id = pipeline.data_source_id if pipeline else None
    budgets = session.scalars(
        select(CostBudget).where(CostBudget.tenant_id == run.tenant_id, CostBudget.active.is_(True))
    ).all()
    estimate = run.estimated_provider_cost
    day_start = datetime.combine(now.date(), time.min, timezone.utc)
    month_start = day_start.replace(day=1)
    for budget in budgets:
        if budget.site_id and budget.site_id != run.site_id:
            continue
        if budget.data_source_id and budget.data_source_id != source_id:
            continue
        if budget.pipeline_id and budget.pipeline_id != run.pipeline_id:
            continue
        if budget.schedule_id and budget.schedule_id != run.schedule_id:
            continue
        if budget.currency != run.currency:
            return BudgetDecision.BLOCK, "budget currency does not match execution currency"
        if budget.per_run_limit is not None and estimate > budget.per_run_limit:
            return BudgetDecision.BLOCK, "estimated cost exceeds per-run budget"
        scope_filters = [CostLedgerEntry.tenant_id == run.tenant_id]
        if budget.site_id:
            scope_filters.append(CostLedgerEntry.site_id == budget.site_id)
        if budget.data_source_id:
            scope_filters.append(CostLedgerEntry.data_source_id == budget.data_source_id)
        if budget.pipeline_id:
            scope_filters.append(CostLedgerEntry.pipeline_id == budget.pipeline_id)
        if budget.schedule_id:
            scope_filters.append(CostLedgerEntry.schedule_id == budget.schedule_id)
        reservation_filters = [
            OrchestrationRun.tenant_id == run.tenant_id,
            OrchestrationRun.status == OrchestrationStatus.RUNNING,
            OrchestrationRun.id != run.id,
        ]
        if budget.site_id:
            reservation_filters.append(OrchestrationRun.site_id == budget.site_id)
        if budget.pipeline_id:
            reservation_filters.append(OrchestrationRun.pipeline_id == budget.pipeline_id)
        if budget.schedule_id:
            reservation_filters.append(OrchestrationRun.schedule_id == budget.schedule_id)
        reserved_statement = select(
            func.coalesce(func.sum(OrchestrationRun.estimated_provider_cost), 0)
        ).where(*reservation_filters)
        if budget.data_source_id:
            reserved_statement = reserved_statement.join(
                PipelineDefinition, PipelineDefinition.id == OrchestrationRun.pipeline_id
            ).where(PipelineDefinition.data_source_id == budget.data_source_id)
        reserved = session.scalar(reserved_statement) or Decimal("0")
        spent_day = session.scalar(
            select(func.coalesce(func.sum(CostLedgerEntry.amount), 0)).where(
                *scope_filters, CostLedgerEntry.occurred_at >= day_start
            )
        )
        spent_month = session.scalar(
            select(func.coalesce(func.sum(CostLedgerEntry.amount), 0)).where(
                *scope_filters, CostLedgerEntry.occurred_at >= month_start
            )
        )
        if (
            budget.daily_limit is not None
            and (spent_day or Decimal("0")) + reserved + estimate > budget.daily_limit
        ):
            return BudgetDecision.BLOCK, "estimated cost exceeds remaining daily budget"
        if (
            budget.monthly_limit is not None
            and (spent_month or Decimal("0")) + reserved + estimate > budget.monthly_limit
        ):
            return BudgetDecision.BLOCK, "estimated cost exceeds remaining monthly budget"
    return BudgetDecision.ALLOW, "within configured budgets"


def mark_stale(session: Session, now: datetime | None = None) -> list[FreshnessState]:
    current = now or utcnow()
    stale: list[FreshnessState] = []
    for state in session.scalars(
        select(FreshnessState).where(FreshnessState.freshness_sla_seconds.is_not(None))
    ):
        reference = state.last_successful_at or state.last_attempted_at
        if reference and current > reference + timedelta(seconds=state.freshness_sla_seconds or 0):
            state.stale_since = state.stale_since or reference + timedelta(
                seconds=state.freshness_sla_seconds or 0
            )
            stub = OrchestrationRun(
                tenant_id=state.tenant_id,
                site_id=state.site_id,
                pipeline_id=state.pipeline_id,
                schedule_id=state.schedule_id,
            )
            open_alert(session, stub, "STALE_SOURCE", "WARNING", "freshness SLA exceeded", current)
            stale.append(state)
    session.commit()
    return stale


def open_alert(
    session: Session,
    run: OrchestrationRun,
    alert_type: str,
    severity: str,
    message: str,
    now: datetime,
) -> OperationalAlert:
    scope = run.schedule_id or run.pipeline_id
    key = f"{alert_type}:{scope}"
    alert = session.scalar(
        select(OperationalAlert).where(
            OperationalAlert.tenant_id == run.tenant_id,
            OperationalAlert.deduplication_key == key,
            OperationalAlert.status == AlertStatus.OPEN,
        )
    )
    if alert:
        alert.last_seen_at = now
        alert.occurrence_count += 1
        alert.message = message
        return alert
    alert = OperationalAlert(
        tenant_id=run.tenant_id,
        site_id=run.site_id,
        pipeline_id=run.pipeline_id,
        schedule_id=run.schedule_id,
        orchestration_run_id=run.id,
        alert_type=alert_type,
        severity=severity,
        deduplication_key=key,
        status=AlertStatus.OPEN,
        message=message,
        opened_at=now,
        last_seen_at=now,
    )
    session.add(alert)
    return alert


def resolve_alert(
    session: Session, tenant_id: uuid.UUID, key: str, now: datetime | None = None
) -> bool:
    alert = session.scalar(
        select(OperationalAlert).where(
            OperationalAlert.tenant_id == tenant_id,
            OperationalAlert.deduplication_key == key,
            OperationalAlert.status == AlertStatus.OPEN,
        )
    )
    if not alert:
        return False
    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = now or utcnow()
    return True
