from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.models import IngestionRun, OrchestrationRun, PipelineDefinition
from gis.orchestration.service import PipelineHandler, PipelineResult

EXECUTABLES = {
    "gsc": "gis-gsc",
    "ga4": "gis-ga4",
    "serp": "gis-serp",
    "experience": "gis-experience",
    "external_search": "gis-search-intelligence",
    "competitive_content": "gis-content-intelligence",
    "competitive_technology": "gis-technology-intelligence",
    "authority_intelligence": "gis-authority-intelligence",
    "market_intelligence": "gis-market-intelligence",
    "collection_planning": "gis-collection-planning",
    "emerging_demand": "gis-emerging-demand",
    "evidence_quality": "gis-evidence-quality",
}


def dbt_handler(session: Session, run: OrchestrationRun) -> PipelineResult:
    project = Path(str(run.configuration_json.get("project_dir", "analytics"))).resolve()
    profiles = Path(str(run.configuration_json.get("profiles_dir", "analytics"))).resolve()
    if not project.is_dir() or not profiles.is_dir():
        raise ValueError("configured dbt project/profiles directory does not exist")
    completed = subprocess.run(
        [
            str(Path(sys.executable).with_name("dbt")),
            "build",
            "--project-dir",
            str(project),
            "--profiles-dir",
            str(profiles),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=int(run.configuration_json.get("timeout_seconds", 3600)),
        env=os.environ.copy(),
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:] or completed.stdout[-2000:])
    return PipelineResult(actual_cost=Decimal("0"))


def collector_cli_handler(session: Session, run: OrchestrationRun) -> PipelineResult:
    pipeline = session.get(PipelineDefinition, run.pipeline_id)
    if not pipeline:
        raise ValueError("pipeline not found")
    executable = EXECUTABLES.get(pipeline.key)
    if not executable:
        raise ValueError(f"no allowlisted collector executable for {pipeline.key}")
    arguments = run.configuration_json.get("arguments")
    if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
        raise ValueError("collector execution requires a string arguments list")
    if run.backfill_start and run.backfill_end:
        arguments = [
            *arguments,
            "--start-date",
            run.backfill_start.isoformat(),
            "--end-date",
            run.backfill_end.isoformat(),
        ]
    started = datetime.now().astimezone()
    completed = subprocess.run(
        [executable, *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=int(run.configuration_json.get("timeout_seconds", 3600)),
        env=os.environ.copy(),
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:] or completed.stdout[-2000:])
    ingestion_run = None
    if run.data_source_connection_id:
        ingestion_run = session.scalar(
            select(IngestionRun)
            .where(
                IngestionRun.data_source_connection_id == run.data_source_connection_id,
                IngestionRun.created_at >= started,
            )
            .order_by(IngestionRun.created_at.desc())
            .limit(1)
        )
    actual = Decimal(str(run.configuration_json.get("actual_cost", run.estimated_provider_cost)))
    return PipelineResult(
        ingestion_run_id=ingestion_run.id if ingestion_run else None,
        actual_cost=actual,
        currency=run.currency,
    )


def competitive_events_handler(session: Session, run: OrchestrationRun) -> PipelineResult:
    from gis.competitive_events.service import SynthesisService
    from gis.models import CompetitiveEventDomain

    if not run.site_id:
        raise ValueError("competitive event synthesis requires a site")
    now = datetime.now().astimezone()
    start_date = run.backfill_start or now.date()
    end_date = run.backfill_end or now.date()
    domains = run.configuration_json.get("domains", [item.value for item in CompetitiveEventDomain])
    SynthesisService(session).synthesize(
        run.tenant_id,
        run.site_id,
        [CompetitiveEventDomain(item) for item in domains],
        datetime.combine(start_date, datetime.min.time(), timezone.utc),
        datetime.combine(end_date, datetime.max.time(), timezone.utc),
    )
    return PipelineResult(actual_cost=Decimal("0"))


def local_processing_handler(session: Session, run: OrchestrationRun) -> PipelineResult:
    """Run allowlisted database-only intelligence processors with no provider access."""
    pipeline = session.get(PipelineDefinition, run.pipeline_id)
    if not pipeline or not run.site_id:
        raise ValueError("local processing requires a pipeline and site scope")
    market_id = run.configuration_json.get("market_id")
    if (
        pipeline.key
        in {
            "market_intelligence",
            "collection_planning",
            "emerging_demand",
        }
        and not market_id
    ):
        raise ValueError("market-scoped local processing requires market_id")
    if pipeline.key == "market_intelligence":
        from gis.market_intelligence.service import MarketIntelligenceService
        from gis.models import DataRightsPolicy, MarketDefinition, SerpObservation

        market = session.get(MarketDefinition, market_id)
        configured_policy_id = run.rights_policy_id or run.configuration_json.get(
            "rights_policy_id"
        )
        policy = session.get(DataRightsPolicy, configured_policy_id)
        if not market or market.tenant_id != run.tenant_id or market.site_id != run.site_id:
            raise ValueError("configured market is outside the orchestration scope")
        if not policy or policy.tenant_id != run.tenant_id:
            raise ValueError("market processing requires a tenant-scoped rights policy")
        effective_date = session.scalar(
            select(func.max(SerpObservation.observed_date)).where(
                SerpObservation.tenant_id == run.tenant_id,
                SerpObservation.site_id == run.site_id,
                SerpObservation.effective_end.is_(None),
            )
        )
        if not effective_date:
            raise ValueError("market processing requires stored current SERP evidence")
        MarketIntelligenceService(session).observe(market, effective_date, policy)
    elif pipeline.key == "collection_planning":
        from gis.collection_planning.service import CollectionPlanningService
        from gis.models import MarketDefinition

        market = session.get(MarketDefinition, market_id)
        if not market or market.tenant_id != run.tenant_id or market.site_id != run.site_id:
            raise ValueError("configured market is outside the orchestration scope")
        planning_service = CollectionPlanningService(session)
        planning_service.discover(market)
        planning_service.plan(market)
    elif pipeline.key == "emerging_demand":
        from gis.emerging_demand.service import EmergingDemandService
        from gis.models import MarketDefinition

        market = session.get(MarketDefinition, market_id)
        if not market or market.tenant_id != run.tenant_id or market.site_id != run.site_id:
            raise ValueError("configured market is outside the orchestration scope")
        demand_service = EmergingDemandService(session)
        demand_service.materialize_stored_evidence(market)
        demand_service.analyze(run.tenant_id, run.site_id, market.id)
    elif pipeline.key == "evidence_quality":
        from gis.evidence_quality.service import EvidenceQualityService

        EvidenceQualityService(session).assess(run.tenant_id, run.site_id)
    elif pipeline.key == "opportunity_detection":
        from gis.opportunities.service import OpportunityService

        OpportunityService(session).detect(run.tenant_id, run.site_id)
    else:
        raise ValueError(f"pipeline {pipeline.key} is not an allowlisted local processor")
    return PipelineResult(actual_cost=Decimal("0"))


def default_handlers() -> dict[str, PipelineHandler]:
    return {
        "DBT": dbt_handler,
        "COLLECTOR_CLI": collector_cli_handler,
        "COMPETITIVE_EVENTS": competitive_events_handler,
        "LOCAL_PROCESSING": local_processing_handler,
    }
