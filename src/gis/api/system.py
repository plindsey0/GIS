from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from gis.api.errors import ApiError
from gis.api.workbench import encoded, row_data
from gis.models import (
    CostBudget,
    CostLedgerEntry,
    DataAsset,
    DataAssetLineage,
    DataAssetSource,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    ExecutionAttempt,
    FreshnessState,
    IngestionRun,
    OrchestrationRun,
    PipelineDefinition,
    PipelineDependency,
    ScheduleDefinition,
)
from gis.orchestration.schedule import next_occurrence

PIPELINE_PURPOSES = {
    "gsc": "Collects first-party Google search performance used for visibility, collection planning, evidence, and measurement.",
    "ga4": "Collects first-party behavioral analytics used for traffic, conversion evidence, measurement, and outcomes.",
    "experience": "Collects PageSpeed LAB and available CrUX FIELD observations without conflating the two measurement types.",
    "external_search": "Collects licensed external keyword and ranking intelligence when explicitly enabled and budgeted.",
    "serp": "Collects governed search-result observations for tracked queries when explicitly enabled and budgeted.",
    "market_intelligence": "Transforms stored SERP and demand evidence into bounded market structure and visibility observations.",
    "emerging_demand": "Transforms stored keyword history into deterministic demand observations and signals.",
    "evidence_quality": "Evaluates identity, source independence, corroboration, conflicts, rights, and sufficiency into governed evidence packages.",
    "opportunity_detection": "Applies transparent detector policies to governed evidence packages; it does not manufacture opportunities.",
    "collection_planning": "Prioritizes discovered query, domain, and URL targets under evidence, rights, capability, and budget constraints.",
    "competitive_events": "Synthesizes stored competitive observations into deterministic competitive events.",
    "dbt_core": "Builds tested analytical transformations and marts from governed source tables.",
    "ai_recommendations": "Produces reviewable recommendation candidates only after qualifying opportunities; production AI is not configured.",
}


def cron_text(expression: str, timezone_name: str) -> str:
    minute, hour, day, month, weekday = expression.split()
    days = {
        "0": "Sunday",
        "1": "Monday",
        "2": "Tuesday",
        "3": "Wednesday",
        "4": "Thursday",
        "5": "Friday",
        "6": "Saturday",
    }
    if day == "*" and month == "*" and weekday == "*" and minute.isdigit() and hour.isdigit():
        suffix = "AM" if int(hour) < 12 else "PM"
        display_hour = int(hour) % 12 or 12
        return f"Every day at {display_hour}:{int(minute):02d} {suffix} ({timezone_name})"
    if day == "*" and month == "*" and weekday in days and minute.isdigit() and hour.isdigit():
        suffix = "AM" if int(hour) < 12 else "PM"
        display_hour = int(hour) % 12 or 12
        return (
            f"Every {days[weekday]} at {display_hour}:{int(minute):02d} {suffix} ({timezone_name})"
        )
    return f"Scheduled by cron in {timezone_name}; raw expression is available in metadata."


def _expected_occurrences(
    schedule: ScheduleDefinition, start: datetime, end: datetime
) -> list[datetime]:
    if schedule.status.value != "ENABLED":
        return []
    result: list[datetime] = []
    cursor = start
    while True:
        occurrence = next_occurrence(schedule.cron_expression, schedule.timezone, cursor)
        if occurrence > end:
            break
        result.append(occurrence)
        cursor = occurrence
    return result


def _reliability(
    schedule: Optional[ScheduleDefinition], runs: list[OrchestrationRun], now: datetime
) -> dict[str, Any]:
    if not schedule or schedule.status.value != "ENABLED":
        return {
            "state": "DISABLED" if schedule else "NOT_APPLICABLE",
            "history": "NOT_APPLICABLE",
            "expected_runs": 0,
            "attempted_runs": len(runs),
            "missed_runs": 0,
        }
    since = max(now - timedelta(days=30), schedule.created_at)
    recent = [run for run in runs if run.requested_at >= since]
    expected = _expected_occurrences(schedule, since, now)
    tolerance = timedelta(minutes=max(15, min(schedule.retry_delay_seconds, 120 * 60) // 60))
    missed = sum(
        not any(
            abs((run.scheduled_for or run.requested_at) - occurrence) <= tolerance for run in recent
        )
        for occurrence in expected
    )
    succeeded = sum(run.status.value == "SUCCEEDED" for run in recent)
    failed = sum(run.status.value in {"FAILED", "PARTIAL"} for run in recent)
    completed = [run for run in recent if run.started_at and run.completed_at]
    durations = [
        (run.completed_at - run.started_at).total_seconds()
        for run in completed
        if run.completed_at and run.started_at
    ]
    insufficient = len(expected) < 2
    return {
        "state": "INSUFFICIENT_HISTORY"
        if insufficient
        else "RELIABLE"
        if not failed and not missed
        else "DEGRADED",
        "history": "INSUFFICIENT_HISTORY" if insufficient else "AVAILABLE",
        "period_days": 30,
        "expected_runs": len(expected),
        "attempted_runs": len(recent),
        "successful_runs": succeeded,
        "failed_runs": failed,
        "missed_runs": missed,
        "success_rate": succeeded / len(recent) if recent else None,
        "median_duration_seconds": statistics.median(durations) if durations else None,
        "missed_definition": f"Enabled-schedule occurrence with no orchestration attempt within ±{int(tolerance.total_seconds() / 60)} minutes. Disabled schedules never accrue misses.",
    }


def _health(
    schedule: Optional[ScheduleDefinition],
    freshness: Optional[FreshnessState],
    runs: list[OrchestrationRun],
) -> tuple[str, str]:
    if schedule and schedule.status.value == "DISABLED":
        return "DISABLED", "The schedule is intentionally disabled."
    if freshness and freshness.consecutive_failures:
        return "FAILING", f"{freshness.consecutive_failures} consecutive execution failure(s)."
    latest = runs[0] if runs else None
    if latest and latest.status.value in {"FAILED", "PARTIAL"}:
        return "FAILING", f"Latest attempt ended {latest.status.value}."
    if freshness and freshness.stale_since:
        return "STALE", "The latest successful output exceeds its configured freshness window."
    if not runs and not (freshness and freshness.last_successful_at):
        return "INSUFFICIENT_HISTORY", "No completed operational history is available."
    return "HEALTHY", "Latest recorded execution succeeded and no staleness is recorded."


class SystemQueries:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _site(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> None:
        from gis.models import Site

        if not self.session.scalar(
            select(Site.id).where(Site.id == site_id, Site.tenant_id == tenant_id)
        ):
            raise ApiError(404, "SITE_NOT_FOUND", "Site not found in tenant scope.")

    def pipelines(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        rows = list(
            self.session.scalars(
                select(PipelineDefinition)
                .where(PipelineDefinition.active.is_(True))
                .order_by(PipelineDefinition.name)
            )
        )
        items = [self.pipeline_summary(row, tenant_id, site_id) for row in rows]
        return {
            "items": items,
            "total": len(items),
            "health_counts": dict(
                __import__("collections").Counter(item["health"] for item in items)
            ),
        }

    def pipeline_summary(
        self, pipeline: PipelineDefinition, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> dict[str, Any]:
        schedule = self.session.scalar(
            select(ScheduleDefinition)
            .where(
                ScheduleDefinition.pipeline_id == pipeline.id,
                ScheduleDefinition.tenant_id == tenant_id,
                or_(ScheduleDefinition.site_id == site_id, ScheduleDefinition.site_id.is_(None)),
            )
            .order_by(ScheduleDefinition.created_at.desc())
            .limit(1)
        )
        freshness = self.session.scalar(
            select(FreshnessState)
            .where(
                FreshnessState.pipeline_id == pipeline.id,
                FreshnessState.tenant_id == tenant_id,
                or_(FreshnessState.site_id == site_id, FreshnessState.site_id.is_(None)),
            )
            .limit(1)
        )
        runs = list(
            self.session.scalars(
                select(OrchestrationRun)
                .where(
                    OrchestrationRun.pipeline_id == pipeline.id,
                    OrchestrationRun.tenant_id == tenant_id,
                    or_(OrchestrationRun.site_id == site_id, OrchestrationRun.site_id.is_(None)),
                )
                .order_by(OrchestrationRun.requested_at.desc())
                .limit(100)
            )
        )
        health, reason = _health(schedule, freshness, runs)
        return {
            "key": pipeline.key,
            "label": pipeline.name,
            "name": pipeline.name,
            "purpose": PIPELINE_PURPOSES.get(
                pipeline.key,
                f"Registered {pipeline.handler_key.casefold().replace('_', ' ')} workflow.",
            ),
            "handler_type": pipeline.handler_key,
            "classification": "EXTERNAL_COLLECTOR"
            if pipeline.handler_key == "COLLECTOR_CLI"
            else "LOCAL_PROCESSING",
            "active": pipeline.active,
            "paid_provider": pipeline.paid_provider,
            "health": health,
            "health_reason": reason,
            "schedule_status": schedule.status.value if schedule else "NOT_CONFIGURED",
            "cadence": cron_text(schedule.cron_expression, schedule.timezone) if schedule else None,
            "latest_success": encoded(freshness.last_successful_at)
            if freshness
            else encoded(
                next((run.completed_at for run in runs if run.status.value == "SUCCEEDED"), None)
            ),
            "run_count": len(runs),
            "href": f"/system/pipelines/{pipeline.key}",
        }

    def pipeline_detail(self, key: str, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        pipeline = self.session.scalar(
            select(PipelineDefinition).where(PipelineDefinition.key == key)
        )
        if not pipeline:
            raise ApiError(404, "PIPELINE_NOT_FOUND", "Pipeline not found.")
        summary = self.pipeline_summary(pipeline, tenant_id, site_id)
        schedule = self.session.scalar(
            select(ScheduleDefinition)
            .where(
                ScheduleDefinition.pipeline_id == pipeline.id,
                ScheduleDefinition.tenant_id == tenant_id,
                or_(ScheduleDefinition.site_id == site_id, ScheduleDefinition.site_id.is_(None)),
            )
            .order_by(ScheduleDefinition.created_at.desc())
            .limit(1)
        )
        runs = list(
            self.session.scalars(
                select(OrchestrationRun)
                .where(
                    OrchestrationRun.pipeline_id == pipeline.id,
                    OrchestrationRun.tenant_id == tenant_id,
                    or_(OrchestrationRun.site_id == site_id, OrchestrationRun.site_id.is_(None)),
                )
                .order_by(OrchestrationRun.requested_at.desc())
                .limit(500)
            )
        )
        upstream_alias = aliased(PipelineDefinition)
        downstream_alias = aliased(PipelineDefinition)
        upstream = list(
            self.session.scalars(
                select(upstream_alias)
                .join(
                    PipelineDependency, PipelineDependency.upstream_pipeline_id == upstream_alias.id
                )
                .where(
                    PipelineDependency.downstream_pipeline_id == pipeline.id,
                    PipelineDependency.tenant_id == tenant_id,
                    or_(
                        PipelineDependency.site_id == site_id, PipelineDependency.site_id.is_(None)
                    ),
                )
            )
        )
        downstream = list(
            self.session.scalars(
                select(downstream_alias)
                .join(
                    PipelineDependency,
                    PipelineDependency.downstream_pipeline_id == downstream_alias.id,
                )
                .where(
                    PipelineDependency.upstream_pipeline_id == pipeline.id,
                    PipelineDependency.tenant_id == tenant_id,
                    or_(
                        PipelineDependency.site_id == site_id, PipelineDependency.site_id.is_(None)
                    ),
                )
            )
        )
        now = datetime.now(timezone.utc)
        ledger = list(
            self.session.scalars(
                select(CostLedgerEntry).where(
                    CostLedgerEntry.pipeline_id == pipeline.id,
                    CostLedgerEntry.tenant_id == tenant_id,
                    or_(CostLedgerEntry.site_id == site_id, CostLedgerEntry.site_id.is_(None)),
                )
            )
        )
        budgets = list(
            self.session.scalars(
                select(CostBudget).where(
                    CostBudget.tenant_id == tenant_id,
                    CostBudget.active.is_(True),
                    or_(CostBudget.pipeline_id == pipeline.id, CostBudget.pipeline_id.is_(None)),
                    or_(CostBudget.site_id == site_id, CostBudget.site_id.is_(None)),
                )
            )
        )
        total_cost = sum((entry.amount for entry in ledger), Decimal("0"))
        month_cost = sum(
            (
                entry.amount
                for entry in ledger
                if entry.occurred_at
                >= now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            ),
            Decimal("0"),
        )
        return {
            **summary,
            "description": summary["purpose"],
            "technical_id": str(pipeline.id),
            "configuration": {
                key: value
                for key, value in pipeline.configuration_json.items()
                if "credential" not in key.casefold() and "secret" not in key.casefold()
            },
            "source": self.source_summary(
                self.session.get(DataSource, pipeline.data_source_id), tenant_id, site_id
            )
            if pipeline.data_source_id
            else None,
            "schedule": {
                **row_data(schedule),
                "human_cadence": cron_text(schedule.cron_expression, schedule.timezone),
            }
            if schedule
            else None,
            "lineage": {
                "upstream_pipelines": [
                    {"key": item.key, "name": item.name, "href": f"/system/pipelines/{item.key}"}
                    for item in upstream
                ],
                "downstream_pipelines": [
                    {"key": item.key, "name": item.name, "href": f"/system/pipelines/{item.key}"}
                    for item in downstream
                ],
            },
            "reliability": _reliability(schedule, runs, now),
            "volume": {
                "total_runs": len(runs),
                "successful_runs": sum(run.status.value == "SUCCEEDED" for run in runs),
                "external_records_received": sum(self._records_received(run) for run in runs),
                "derived_processing": pipeline.handler_key != "COLLECTOR_CLI",
            },
            "cost": {
                "classification": "PAID_PROVIDER"
                if pipeline.paid_provider
                else "LOCAL_OR_ZERO_MONETARY_COST",
                "latest_run": encoded(runs[0].actual_provider_cost) if runs else None,
                "current_month": encoded(month_cost),
                "lifetime": encoded(total_cost),
                "currency": pipeline.currency,
                "budgets": [row_data(item) for item in budgets],
            },
            "runs": [self.run_summary(run, pipeline) for run in runs[:100]],
        }

    def _ingestion(self, run: OrchestrationRun) -> Optional[IngestionRun]:
        return (
            self.session.get(IngestionRun, run.ingestion_run_id) if run.ingestion_run_id else None
        )

    def _records_received(self, run: OrchestrationRun) -> int:
        ingestion = self._ingestion(run)
        return ingestion.records_received if ingestion else 0

    def run_summary(
        self, run: OrchestrationRun, pipeline: Optional[PipelineDefinition] = None
    ) -> dict[str, Any]:
        ingestion = self._ingestion(run)
        duration = (
            (run.completed_at - run.started_at).total_seconds()
            if run.started_at and run.completed_at
            else None
        )
        return {
            "id": str(run.id),
            "label": f"{pipeline.name if pipeline else 'Pipeline'} run",
            "pipeline_key": pipeline.key if pipeline else None,
            "pipeline_name": pipeline.name if pipeline else None,
            "status": run.status.value,
            "trigger": run.trigger_type.value,
            "requested_at": encoded(run.requested_at),
            "started_at": encoded(run.started_at),
            "completed_at": encoded(run.completed_at),
            "duration_seconds": duration,
            "records_received": ingestion.records_received if ingestion else None,
            "records_inserted": ingestion.records_inserted if ingestion else None,
            "errors": ingestion.error_count if ingestion else (1 if run.error_detail else 0),
            "cost": encoded(run.actual_provider_cost),
            "currency": run.currency,
            "href": f"/system/runs/{run.id}",
        }

    def runs(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        *,
        page: int,
        limit: int,
        status: Optional[str] = None,
        pipeline_key: Optional[str] = None,
    ) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        filters: list[Any] = [
            OrchestrationRun.tenant_id == tenant_id,
            or_(OrchestrationRun.site_id == site_id, OrchestrationRun.site_id.is_(None)),
        ]
        if status:
            filters.append(OrchestrationRun.status == status)
        query = select(OrchestrationRun, PipelineDefinition).join(PipelineDefinition)
        if pipeline_key:
            filters.append(PipelineDefinition.key == pipeline_key)
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(OrchestrationRun)
                .join(PipelineDefinition)
                .where(*filters)
            )
            or 0
        )
        rows = self.session.execute(
            query.where(*filters)
            .order_by(OrchestrationRun.requested_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        return {
            "items": [self.run_summary(run, pipeline) for run, pipeline in rows],
            "page": page,
            "limit": limit,
            "total": total,
        }

    def run_detail(
        self, run_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> dict[str, Any]:
        row = self.session.execute(
            select(OrchestrationRun, PipelineDefinition)
            .join(PipelineDefinition)
            .where(
                OrchestrationRun.id == run_id,
                OrchestrationRun.tenant_id == tenant_id,
                or_(OrchestrationRun.site_id == site_id, OrchestrationRun.site_id.is_(None)),
            )
        ).one_or_none()
        if not row:
            raise ApiError(404, "RUN_NOT_FOUND", "Run not found in site scope.")
        run, pipeline = row
        ingestion = self._ingestion(run)
        attempts = list(
            self.session.scalars(
                select(ExecutionAttempt)
                .where(ExecutionAttempt.orchestration_run_id == run.id)
                .order_by(ExecutionAttempt.attempt_number)
            )
        )
        policy = (
            self.session.get(DataRightsPolicy, run.rights_policy_id)
            if run.rights_policy_id
            else None
        )
        return {
            **self.run_summary(run, pipeline),
            "resource_type": "orchestration_run",
            "error_classification": run.error_classification,
            "error_detail": run.error_detail,
            "attempts": [row_data(item) for item in attempts],
            "ingestion_run": row_data(ingestion, exclude={"source_cursor"}) if ingestion else None,
            "rights_policy": row_data(policy) if policy else None,
            "configuration": {
                key: value
                for key, value in run.configuration_json.items()
                if "credential" not in key.casefold() and "secret" not in key.casefold()
            },
            "pipeline": {
                "key": pipeline.key,
                "name": pipeline.name,
                "href": f"/system/pipelines/{pipeline.key}",
            },
        }

    def sources(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        sources = list(self.session.scalars(select(DataSource).order_by(DataSource.name)))
        items = [self.source_summary(source, tenant_id, site_id) for source in sources]
        return {"items": items, "total": len(items)}

    def source_summary(
        self, source: Optional[DataSource], tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> Optional[dict[str, Any]]:
        if not source:
            return None
        connections = list(
            self.session.scalars(
                select(DataSourceConnection).where(
                    DataSourceConnection.data_source_id == source.id,
                    DataSourceConnection.tenant_id == tenant_id,
                    or_(
                        DataSourceConnection.site_id == site_id,
                        DataSourceConnection.site_id.is_(None),
                    ),
                )
            )
        )
        pipelines = list(
            self.session.scalars(
                select(PipelineDefinition).where(PipelineDefinition.data_source_id == source.id)
            )
        )
        runs = list(
            self.session.scalars(
                select(IngestionRun)
                .join(DataSourceConnection)
                .where(
                    DataSourceConnection.data_source_id == source.id,
                    IngestionRun.tenant_id == tenant_id,
                    or_(IngestionRun.site_id == site_id, IngestionRun.site_id.is_(None)),
                )
            )
        )
        policy_id = (
            next((item.rights_policy_id for item in connections if item.rights_policy_id), None)
            or source.default_rights_policy_id
        )
        policy = self.session.get(DataRightsPolicy, policy_id) if policy_id else None
        return {
            "key": source.key,
            "label": source.name,
            "name": source.name,
            "provider": source.provider,
            "type": source.source_type.value,
            "acquisition_method": source.acquisition_method.value,
            "active": source.is_active,
            "connection_status": connections[0].status.value if connections else "NOT_CONFIGURED",
            "rights_status": "REVIEWED" if policy and policy.reviewed_at else "UNKNOWN",
            "last_success": encoded(
                max(
                    (
                        run.completed_at
                        for run in runs
                        if run.status.value == "SUCCEEDED" and run.completed_at
                    ),
                    default=None,
                )
            ),
            "records": sum(run.records_inserted for run in runs),
            "cost": "PAID"
            if any(item.paid_provider for item in pipelines)
            else "ZERO_OR_UNTRACKED",
            "powering": [item.key for item in pipelines],
            "href": f"/system/sources/{source.key}",
        }

    def source_detail(self, key: str, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        source = self.session.scalar(select(DataSource).where(DataSource.key == key))
        if not source:
            raise ApiError(404, "SOURCE_NOT_FOUND", "Data source not found.")
        summary = self.source_summary(source, tenant_id, site_id) or {}
        connections = list(
            self.session.scalars(
                select(DataSourceConnection).where(
                    DataSourceConnection.data_source_id == source.id,
                    DataSourceConnection.tenant_id == tenant_id,
                    or_(
                        DataSourceConnection.site_id == site_id,
                        DataSourceConnection.site_id.is_(None),
                    ),
                )
            )
        )
        assets = list(
            self.session.scalars(
                select(DataAsset)
                .join(DataAssetSource)
                .where(DataAssetSource.data_source_id == source.id)
            )
        )
        downstream_assets = (
            list(
                self.session.scalars(
                    select(DataAsset)
                    .join(DataAssetLineage, DataAssetLineage.downstream_asset_id == DataAsset.id)
                    .where(DataAssetLineage.upstream_asset_id.in_([item.id for item in assets]))
                )
            )
            if assets
            else []
        )
        policies = [
            self.session.get(
                DataRightsPolicy, connection.rights_policy_id or source.default_rights_policy_id
            )
            for connection in connections
        ]
        return {
            **summary,
            "description": source.description
            or f"Registered {source.source_type.value.casefold().replace('_', ' ')} source from {source.provider}.",
            "authoritative_url": source.authoritative_url,
            "terms_url": source.terms_url,
            "connections": [
                {
                    **row_data(item, exclude={"credential_reference", "configuration_json"}),
                    "configuration_present": bool(item.configuration_json),
                    "credential_configured": bool(item.credential_reference),
                }
                for item in connections
            ],
            "rights": [row_data(item) for item in policies if item],
            "assets": [row_data(item) for item in assets],
            "downstream_assets": [row_data(item) for item in downstream_assets],
            "impact": {
                "affected_pipelines": summary.get("powering", []),
                "unmapped_dependencies": not assets and not summary.get("powering"),
            },
            "quota": "Quota telemetry not available",
        }

    def data_flow(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self._site(tenant_id, site_id)
        sources = [
            self.source_summary(item, tenant_id, site_id)
            for item in self.session.scalars(select(DataSource).order_by(DataSource.name))
        ]
        pipelines = list(
            self.session.scalars(
                select(PipelineDefinition)
                .where(PipelineDefinition.active.is_(True))
                .order_by(PipelineDefinition.name)
            )
        )
        dependencies = list(
            self.session.scalars(
                select(PipelineDependency).where(
                    PipelineDependency.tenant_id == tenant_id,
                    or_(
                        PipelineDependency.site_id == site_id, PipelineDependency.site_id.is_(None)
                    ),
                )
            )
        )
        assets = list(
            self.session.scalars(
                select(DataAsset)
                .where(DataAsset.active.is_(True))
                .order_by(DataAsset.layer, DataAsset.canonical_name)
            )
        )
        lineage = list(self.session.scalars(select(DataAssetLineage)))
        pipeline_keys = {item.id: item.key for item in pipelines}
        return {
            "sources": [item for item in sources if item],
            "pipelines": [self.pipeline_summary(item, tenant_id, site_id) for item in pipelines],
            "pipeline_edges": [
                {
                    "from": pipeline_keys.get(item.upstream_pipeline_id),
                    "to": pipeline_keys.get(item.downstream_pipeline_id),
                    "policy": item.policy.value,
                }
                for item in dependencies
            ],
            "assets": [row_data(item) for item in assets],
            "asset_edges": [row_data(item) for item in lineage],
            "methodology": "Edges come only from registered DataSource→Pipeline assignments, PipelineDependency, DataAssetSource, and DataAssetLineage metadata.",
        }
