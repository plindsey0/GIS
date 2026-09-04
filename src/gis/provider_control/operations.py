"""Read-only operational evidence. Never creates events or contacts providers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    CollectionTarget,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExecutionAttempt,
    IngestionRun,
    OrchestrationObligation,
    OrchestrationRun,
    ProviderCapability,
    ProviderCapabilityPolicy,
    ProviderCollectionTarget,
    ProviderDefinition,
    ProviderUsageEvent,
)


def seconds(start: datetime | None, end: datetime | None) -> float | None:
    return (end - start).total_seconds() if start and end and end >= start else None


def timing(
    attempts: list[ExecutionAttempt],
    run: OrchestrationRun,
    obligation: OrchestrationObligation | None,
) -> dict[str, Any]:
    durations = [seconds(a.started_at, a.completed_at) for a in attempts]
    active = (
        sum(d for d in durations if d is not None)
        if durations and all(d is not None for d in durations)
        else None
    )
    successful = [a for a in attempts if a.status.value == "SUCCEEDED"]
    recovered = bool(
        successful
        and any(
            a.status.value == "FAILED" and a.attempt_number < successful[-1].attempt_number
            for a in attempts
        )
    )
    late = (
        max(0, (obligation.satisfied_at - obligation.due_at).total_seconds())
        if obligation and obligation.satisfied_at
        else None
    )
    return {
        "active_execution_duration": active,
        "successful_attempt_duration": seconds(
            successful[-1].started_at, successful[-1].completed_at
        )
        if successful
        else None,
        "run_first_attempt_started_at": attempts[0].started_at if attempts else None,
        "run_last_attempt_completed_at": attempts[-1].completed_at if attempts else None,
        "wall_clock_resolution_time": seconds(attempts[0].started_at, run.completed_at)
        if attempts
        else None,
        "obligation_lateness": late,
        "recovery_latency": late if recovered else None,
        "recovered": recovered,
    }


def resolved_cause(detail: str | None, category: str | None) -> str | None:
    if detail and any(
        t in detail.lower()
        for t in ("referenced credential is unavailable", "credential_unavailable")
    ):
        return "The execution worker could not resolve the configured credential"
    return category


def authentication(session: Session, connection: DataSourceConnection) -> dict[str, Any]:
    # Require endpoint evidence, not merely a successful local processing run.
    successes = session.scalars(
        select(IngestionRun)
        .where(
            IngestionRun.data_source_connection_id == connection.id,
            IngestionRun.tenant_id == connection.tenant_id,
            IngestionRun.status == "SUCCEEDED",
        )
        .order_by(IngestionRun.completed_at.desc())
    ).all()
    success = next(
        (
            i
            for i in successes
            if i.completed_at
            and (
                i.source_metadata.get("provider_task_id")
                or (
                    i.collector_name == "gis.integrations.builtwith"
                    and i.source_metadata.get("provider_response_validated") is True
                )
            )
        ),
        None,
    )
    failed = session.scalar(
        select(ExecutionAttempt)
        .join(OrchestrationRun)
        .where(
            OrchestrationRun.data_source_connection_id == connection.id,
            OrchestrationRun.tenant_id == connection.tenant_id,
            ExecutionAttempt.failure_category == "AUTHENTICATION_FAILED",
        )
        .order_by(ExecutionAttempt.started_at.desc())
        .limit(1)
    )
    succeeded_at = success.completed_at if success else None
    failed_at = (failed.completed_at or failed.started_at) if failed else None
    source = session.get(DataSource, connection.data_source_id)
    if source and source.key == "builtwith":
        from gis.models import ProviderAccountTelemetry

        telemetry = session.scalars(
            select(ProviderAccountTelemetry).where(
                ProviderAccountTelemetry.connection_id == connection.id,
                ProviderAccountTelemetry.tenant_id == connection.tenant_id,
            )
        ).all()
        account_success = max(
            (row.checked_at for row in telemetry if row.status == "CURRENT"), default=None
        )
        account_failure = max(
            (
                row.checked_at
                for row in telemetry
                if row.failure_category == "AUTHENTICATION_FAILED"
            ),
            default=None,
        )
        succeeded_at = max(filter(None, [succeeded_at, account_success]), default=None)
        failed_at = max(filter(None, [failed_at, account_failure]), default=None)
    state = (
        "AUTHENTICATION_FAILED"
        if failed_at and (not succeeded_at or failed_at >= succeeded_at)
        else "VALIDATED"
        if succeeded_at
        else "NOT_INDEPENDENTLY_VALIDATED"
    )
    return {
        "authentication_state": state,
        "last_authentication_success_at": succeeded_at,
        "last_authentication_failure_at": failed_at,
        "authentication_explanation": "Historical endpoint acceptance for this connection; not proof that a rotated credential remains valid. Account telemetry is not technology collection acceptance."
        if succeeded_at
        else "No successful provider-task evidence is available; secret resolution alone is insufficient.",
    }


def run_evidence(session: Session, run: OrchestrationRun) -> dict[str, Any]:
    attempts = list(
        session.scalars(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.orchestration_run_id == run.id)
            .order_by(ExecutionAttempt.attempt_number)
        )
    )
    obligation = (
        session.get(OrchestrationObligation, run.obligation_id) if run.obligation_id else None
    )
    ingestion = session.get(IngestionRun, run.ingestion_run_id) if run.ingestion_run_id else None
    connection = (
        session.get(DataSourceConnection, run.data_source_connection_id)
        if run.data_source_connection_id
        else None
    )
    source = session.get(DataSource, connection.data_source_id) if connection else None
    key = (
        "google_pagespeed"
        if source and source.key in {"pagespeed", "crux"}
        else source.key
        if source
        else None
    )
    provider = (
        session.scalar(select(ProviderDefinition).where(ProviderDefinition.provider_key == key))
        if key
        else None
    )
    import uuid

    target_key = run.configuration_json.get("provider_target_id")
    try:
        target = (
            session.get(ProviderCollectionTarget, uuid.UUID(str(target_key)))
            if target_key
            else None
        )
    except ValueError:
        target = None
    cp = session.get(ProviderCapabilityPolicy, target.capability_policy_id) if target else None
    cap = session.get(ProviderCapability, cp.capability_id) if cp else None
    canonical = (
        session.get(CollectionTarget, target.target_reference_id)
        if target and target.target_reference_id
        else None
    )
    if canonical is None and target and target.target_type in {"QUERY", "DOMAIN", "URL"}:
        matches = session.scalars(
            select(CollectionTarget).where(
                CollectionTarget.tenant_id == run.tenant_id,
                CollectionTarget.site_id == run.site_id,
                CollectionTarget.target_type == target.target_type,
                CollectionTarget.normalized_identity == target.target_value,
            )
        ).all()
        # Never guess between markets/locale-specific canonical identities.
        canonical = matches[0] if len(matches) == 1 else None
    uses = (
        list(
            session.scalars(
                select(ProviderUsageEvent).where(
                    ProviderUsageEvent.ingestion_run_id == ingestion.id,
                    ProviderUsageEvent.tenant_id == run.tenant_id,
                    ProviderUsageEvent.data_source_connection_id == run.data_source_connection_id,
                )
            )
        )
        if ingestion
        else []
    )
    currencies = {u.currency for u in uses}
    cost = (
        sum((u.actual_cost for u in uses if u.actual_cost is not None), Decimal(0))
        if uses and all(u.actual_cost is not None for u in uses) and len(currencies) == 1
        else None
    )
    if not uses and not provider:
        cost = run.actual_provider_cost
    currency = next(iter(currencies)) if len(currencies) == 1 else run.currency
    times = timing(attempts, run, obligation)
    failures = [a for a in attempts if a.status.value == "FAILED"]
    cause = (
        resolved_cause(
            failures[0].error_detail,
            failures[0].failure_category.value if failures[0].failure_category else None,
        )
        if failures
        else None
    )
    rights_id = run.rights_policy_id or (ingestion.rights_policy_id if ingestion else None)
    rights = session.get(DataRightsPolicy, rights_id) if rights_id else None
    from gis.orchestration.ingestion import ingestion_failure

    failure = ingestion_failure(ingestion) if ingestion else None
    inconsistent = run.status.value == "SUCCEEDED" and failure is not None
    if failure:
        cause = str(failure)
    if inconsistent:
        times["successful_attempt_duration"] = None
        times["recovered"] = False
    return {
        **times,
        "recorded_status": run.status.value,
        "status": "FAILED" if inconsistent else run.status.value,
        "effective_failure_category": failure.category.value if failure else None,
        "state_interpretation": "Derived failure: the recorded run says SUCCEEDED, but required ingestion failed or contains errors. Historical records are unchanged."
        if inconsistent
        else None,
        "provider_key": key if provider else None,
        "provider_name": provider.display_name if provider else None,
        "provider_href": f"/providers/{key}" if provider else None,
        "capability_key": cap.capability_key if cap else None,
        "capability_name": cap.display_name if cap else None,
        "request_count": sum(u.request_count for u in uses)
        if uses
        else run.configuration_json.get("request_count"),
        "target_display_name": target.target_value if target else "Not recorded",
        "target_href": f"/collection/{canonical.id}" if canonical else None,
        "source_href": f"/system/sources/{source.key}" if source else None,
        "attempt_count": len(attempts),
        "obligation_id": str(run.obligation_id) if run.obligation_id else None,
        "due_at": obligation.due_at if obligation else None,
        "outcome": "FAILED"
        if inconsistent
        else "RECOVERED"
        if times["recovered"] and obligation and obligation.status.value == "SATISFIED"
        else run.status.value,
        "provider_cost_exact": str(cost) if cost is not None else None,
        "provider_cost_display": str(cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if cost is not None
        else None,
        "cost_state": "ACTUAL" if cost is not None else "UNKNOWN",
        "currency": currency,
        "failure_summary": cause,
        "recovery_summary": "The initial collection failed. A later retry succeeded and satisfied the required collection; original attempts remain in history."
        if times["recovered"]
        else None,
        "attempt_timeline": [
            {
                "number": a.attempt_number,
                "status": a.status.value,
                "effective_status": "FAILED"
                if a.ingestion_run_id
                and (child := session.get(IngestionRun, a.ingestion_run_id))
                and ingestion_failure(child)
                else a.status.value,
                "trigger": a.trigger_type.value,
                "started_at": a.started_at,
                "completed_at": a.completed_at,
                "duration": seconds(a.started_at, a.completed_at),
                "resolved_cause": resolved_cause(
                    a.error_detail, a.failure_category.value if a.failure_category else None
                ),
                "recorded_classification": a.error_classification,
                "cost": str(a.actual_provider_cost) if a.actual_provider_cost is not None else None,
            }
            for a in attempts
        ],
        "rights_summary": {
            "policy": rights.name,
            "raw_storage": rights.raw_storage_allowed.value,
            "derived_analysis": rights.deterministic_analysis_allowed.value,
            "derived_storage": rights.derived_storage_allowed.value,
        }
        if rights
        else None,
        "cost_links": [
            {
                "usage_id": str(u.id),
                "ingestion_id": str(u.ingestion_run_id),
                "provider_task_id": u.provider_job_id
                or (ingestion.source_metadata.get("provider_task_id") if ingestion else None),
            }
            for u in uses
        ],
    }


def provider_operations(
    session: Session, connection_id: Any, tenant_id: Any, site_id: Any
) -> dict[str, Any]:
    from gis.api.system import SystemQueries
    from gis.models import PipelineDefinition

    if not connection_id:
        return {
            "activity": [],
            "current_incidents": 0,
            "reliability": {"expected": 0, "on_time": 0, "recovered_late": 0, "missed": 0},
        }
    rows = session.execute(
        select(OrchestrationRun, PipelineDefinition)
        .join(PipelineDefinition)
        .where(
            OrchestrationRun.tenant_id == tenant_id,
            OrchestrationRun.site_id == site_id,
            OrchestrationRun.data_source_connection_id == connection_id,
        )
        .order_by(OrchestrationRun.requested_at.desc())
        .limit(50)
    ).all()
    seen = set()
    activity: list[dict[str, Any]] = []
    for run, pipeline in rows:
        identity = run.obligation_id or run.id
        if identity not in seen and len(activity) < 10:
            activity.append(SystemQueries(session).run_summary(run, pipeline))
            seen.add(identity)
    now = datetime.now(timezone.utc)
    obligations = list(
        session.scalars(
            select(OrchestrationObligation).where(
                OrchestrationObligation.tenant_id == tenant_id,
                OrchestrationObligation.site_id == site_id,
                OrchestrationObligation.data_source_connection_id == connection_id,
                OrchestrationObligation.due_at <= now,
            )
        )
    )
    current = [
        o for o in obligations if o.status.value not in {"SATISFIED", "CANCELLED", "SKIPPED"}
    ]
    recent = [o for o in obligations if o.due_at >= now - timedelta(days=30)]
    ontime = sum(o.satisfied_at is not None and o.satisfied_at <= o.due_at for o in recent)
    late = sum(o.satisfied_at is not None and o.satisfied_at > o.due_at for o in recent)
    return {
        "activity": activity,
        "current_incidents": len(current),
        "reliability": {
            "expected": len(recent),
            "on_time": ontime,
            "recovered_late": late,
            "missed": sum(
                o.status.value not in {"SATISFIED", "CANCELLED", "SKIPPED"} for o in recent
            ),
        },
    }
