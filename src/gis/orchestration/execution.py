from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
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
}


def dbt_handler(session: Session, run: OrchestrationRun) -> PipelineResult:
    project = Path(str(run.configuration_json.get("project_dir", "analytics"))).resolve()
    profiles = Path(str(run.configuration_json.get("profiles_dir", "analytics"))).resolve()
    if not project.is_dir() or not profiles.is_dir():
        raise ValueError("configured dbt project/profiles directory does not exist")
    completed = subprocess.run(
        ["dbt", "build", "--project-dir", str(project), "--profiles-dir", str(profiles)],
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


def default_handlers() -> dict[str, PipelineHandler]:
    return {
        "DBT": dbt_handler,
        "COLLECTOR_CLI": collector_cli_handler,
        "COMPETITIVE_EVENTS": competitive_events_handler,
    }
