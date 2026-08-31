from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    DataSource,
    DependencyPolicy,
    PipelineDefinition,
    PipelineDependency,
    ScheduleDefinition,
    ScheduleStatus,
    Site,
    Tenant,
)
from gis.orchestration.schedule import next_occurrence


@dataclass(frozen=True)
class Cadence:
    key: str
    name: str
    cron: str
    source_key: str | None
    handler: str
    paid: bool = False
    enabled: bool = False


VAHOMEMATH_CADENCE = (
    Cadence("gsc", "GSC daily", "15 4 * * *", "google_search_console", "COLLECTOR_CLI"),
    Cadence("ga4", "GA4 daily", "45 4 * * *", "ga4", "COLLECTOR_CLI"),
    Cadence("dbt_core", "dbt core daily", "30 6 * * *", None, "DBT"),
    Cadence("serp", "Priority SERPs daily", "0 7 * * *", "dataforseo", "COLLECTOR_CLI", True),
    Cadence(
        "external_search",
        "External search weekly",
        "0 8 * * 1",
        "dataforseo",
        "COLLECTOR_CLI",
        True,
    ),
    Cadence(
        "competitive_content",
        "Competitive content weekly",
        "0 9 * * 2",
        "direct_http",
        "COLLECTOR_CLI",
    ),
    Cadence(
        "competitive_technology",
        "Competitive technology weekly",
        "0 10 * * 3",
        "direct_technology",
        "COLLECTOR_CLI",
    ),
    Cadence(
        "authority_intelligence",
        "Authority intelligence weekly",
        "0 11 * * 5",
        "dataforseo",
        "COLLECTOR_CLI",
        True,
    ),
    Cadence(
        "market_intelligence",
        "Market intelligence weekly",
        "30 11 * * 5",
        None,
        "COLLECTOR_CLI",
    ),
    Cadence(
        "collection_planning",
        "Collection planning weekly",
        "0 12 * * 5",
        None,
        "COLLECTOR_CLI",
    ),
    Cadence(
        "emerging_demand",
        "Emerging demand weekly",
        "30 12 * * 5",
        None,
        "COLLECTOR_CLI",
    ),
    Cadence(
        "evidence_quality",
        "Evidence quality weekly",
        "0 13 * * 5",
        None,
        "COLLECTOR_CLI",
    ),
    Cadence(
        "opportunity_detection",
        "Opportunity detection daily",
        "30 13 * * *",
        None,
        "COLLECTOR_CLI",
    ),
    Cadence("experience", "PageSpeed and CrUX weekly", "0 11 * * 4", "pagespeed", "COLLECTOR_CLI"),
    Cadence(
        "competitive_events", "Competitive events daily", "0 12 * * *", None, "COMPETITIVE_EVENTS"
    ),
)


def seed_vahomemath_cadence(session: Session) -> list[ScheduleDefinition]:
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = (
        session.scalar(select(Site).where(Site.tenant_id == tenant.id, Site.slug == "vahomemath"))
        if tenant
        else None
    )
    if not tenant or not site:
        raise ValueError("run gis-seed before seeding orchestration cadence")
    schedules: list[ScheduleDefinition] = []
    pipelines: dict[str, PipelineDefinition] = {}
    for item in VAHOMEMATH_CADENCE:
        source = (
            session.scalar(select(DataSource).where(DataSource.key == item.source_key))
            if item.source_key
            else None
        )
        pipeline = session.scalar(
            select(PipelineDefinition).where(PipelineDefinition.key == item.key)
        )
        if not pipeline:
            pipeline = PipelineDefinition(
                key=item.key,
                name=item.name.removesuffix(" daily").removesuffix(" weekly"),
                handler_key=item.handler,
                data_source_id=source.id if source else None,
                paid_provider=item.paid,
                default_estimated_cost=Decimal("0"),
            )
            session.add(pipeline)
            session.flush()
        pipelines[item.key] = pipeline
        schedule = session.scalar(
            select(ScheduleDefinition).where(
                ScheduleDefinition.tenant_id == tenant.id,
                ScheduleDefinition.name == item.name,
            )
        )
        if not schedule:
            schedule = ScheduleDefinition(
                tenant_id=tenant.id,
                organization_id=site.organization_id,
                site_id=site.id,
                pipeline_id=pipeline.id,
                name=item.name,
                cron_expression=item.cron,
                timezone=site.timezone,
                status=ScheduleStatus.ENABLED
                if item.enabled and not item.paid
                else ScheduleStatus.DISABLED,
                max_attempts=3,
                retry_delay_seconds=300,
                exponential_backoff=True,
                freshness_sla_seconds=172800 if "daily" in item.name.casefold() else 691200,
                configuration_json={"template": True, "requires_operator_configuration": True},
            )
            schedule.next_scheduled_at = next_occurrence(
                item.cron, site.timezone, datetime.now(timezone.utc)
            )
            session.add(schedule)
        schedules.append(schedule)
    for upstream_key, downstream_key in (
        ("gsc", "dbt_core"),
        ("ga4", "dbt_core"),
        ("serp", "competitive_content"),
        ("competitive_content", "competitive_technology"),
        ("serp", "competitive_events"),
        ("external_search", "competitive_events"),
        ("competitive_content", "competitive_events"),
        ("competitive_technology", "competitive_events"),
        ("authority_intelligence", "competitive_events"),
        ("serp", "market_intelligence"),
        ("external_search", "market_intelligence"),
        ("competitive_content", "market_intelligence"),
        ("competitive_technology", "market_intelligence"),
        ("competitive_events", "market_intelligence"),
        ("authority_intelligence", "market_intelligence"),
        ("market_intelligence", "collection_planning"),
        ("market_intelligence", "emerging_demand"),
        ("collection_planning", "emerging_demand"),
        ("market_intelligence", "evidence_quality"),
        ("collection_planning", "evidence_quality"),
        ("emerging_demand", "evidence_quality"),
        ("competitive_events", "evidence_quality"),
        ("authority_intelligence", "evidence_quality"),
        ("market_intelligence", "opportunity_detection"),
        ("collection_planning", "opportunity_detection"),
        ("emerging_demand", "opportunity_detection"),
        ("evidence_quality", "opportunity_detection"),
    ):
        existing = session.scalar(
            select(PipelineDependency).where(
                PipelineDependency.tenant_id == tenant.id,
                PipelineDependency.site_id == site.id,
                PipelineDependency.upstream_pipeline_id == pipelines[upstream_key].id,
                PipelineDependency.downstream_pipeline_id == pipelines[downstream_key].id,
            )
        )
        if not existing:
            session.add(
                PipelineDependency(
                    tenant_id=tenant.id,
                    site_id=site.id,
                    upstream_pipeline_id=pipelines[upstream_key].id,
                    downstream_pipeline_id=pipelines[downstream_key].id,
                    policy=(
                        DependencyPolicy.ALWAYS
                        if downstream_key
                        in {
                            "market_intelligence",
                            "collection_planning",
                            "emerging_demand",
                            "evidence_quality",
                            "opportunity_detection",
                        }
                        else DependencyPolicy.ALL_SUCCESS
                    ),
                )
            )
    session.commit()
    return schedules
