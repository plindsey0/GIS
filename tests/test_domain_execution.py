from __future__ import annotations

import json
import uuid
from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_external_search import FakeProvider, ranking_item
from test_manual_scope import configured, invoke

from gis.api.system import SystemQueries
from gis.integrations.external_search.dataforseo import ExternalSearchProviderError, SearchRequest
from gis.integrations.external_search.service import ExternalSearchCollector
from gis.models import (
    ExecutionAttempt,
    FailureCategory,
    IngestionRun,
    IngestionStatus,
    OrchestrationRun,
    PipelineDefinition,
    ProviderCapabilityPolicy,
    ProviderUsageEvent,
    ScheduleDefinition,
)
from gis.orchestration.service import PipelineResult, Worker
from gis.provider_control.binding import execution_arguments
from gis.provider_control.manual import ManualRequest


def queued_domain(session):
    # Worker rollback must not roll back the fixture's enclosing isolation transaction.
    session.join_transaction_mode = "create_savepoint"
    tenant, site, service = configured(session)
    request = ManualRequest(request_id=uuid.uuid4())
    choices = invoke(session, tenant, site, request)["choices"]
    request.target_ids = [
        uuid.UUID(
            next(c["id"] for c in choices if c["capability_key"] == "DOMAIN_SEARCH_INTELLIGENCE")
        )
    ]
    preview = invoke(session, tenant, site, request)
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    invoke(session, tenant, site, request)
    return tenant, site, session.scalar(select(OrchestrationRun)), service


@pytest.mark.parametrize(
    "mode", ["success", "missing_location", "provider_failure", "processing_failure"]
)
def test_terminal_ingestion_contract_and_accounting(session, monkeypatch, mode):
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    tenant, site, queued, _ = queued_domain(session)
    schedule_before = [
        (s.id, s.status, s.next_scheduled_at, s.cron_expression, s.policy_version)
        for s in session.scalars(select(ScheduleDefinition))
    ]
    calls = []

    class Fixture:
        def collect(self, request):
            calls.append(request)
            if mode == "provider_failure":
                raise ExternalSearchProviderError(
                    "Fixture auth failure",
                    FailureCategory.AUTHENTICATION_FAILED,
                    cost=Decimal("0.01800001"),
                )
            if mode == "processing_failure":
                raise ValueError("Fixture processing exception")
            return FakeProvider([ranking_item()]).collect(request)

    def handler(s, r):
        args = execution_arguments(s, r, s.get(PipelineDefinition, r.pipeline_id))
        assert args[-4:] == ["--location-code", "2840", "--language", "en"]
        ingestion = ExternalSearchCollector(s, Fixture()).sync(
            r.data_source_connection_id,
            site.id,
            SearchRequest(
                "ranked_keywords",
                "vahomemath.com",
                location_code=None if mode == "missing_location" else 2840,
                language_code="en",
            ),
        )
        usage = s.scalar(
            select(ProviderUsageEvent).where(ProviderUsageEvent.ingestion_run_id == ingestion.id)
        )
        return PipelineResult(ingestion_run_id=ingestion.id, actual_cost=usage.actual_cost)

    run = Worker(session, {"COLLECTOR_CLI": handler}, "fixture-worker").run_once(
        queued.available_at + timedelta(seconds=1)
    )
    ingestion = session.get(IngestionRun, run.ingestion_run_id)
    attempt = session.scalar(select(ExecutionAttempt))
    usage = session.scalar(select(ProviderUsageEvent))
    assert attempt.ingestion_run_id == run.ingestion_run_id == usage.ingestion_run_id
    assert usage.request_count == 1
    if mode == "success":
        assert run.status.value == attempt.status.value == ingestion.status.value == "SUCCEEDED"
    else:
        assert run.status.value != "SUCCEEDED"
        assert attempt.status.value == ingestion.status.value == "FAILED"
        assert (
            ingestion.records_received == ingestion.records_inserted == 0
            and ingestion.error_count == 1
        )
        assert usage.actual_cost == (Decimal("0.01800001") if mode == "provider_failure" else None)
        assert usage.status == "FAILED"
        assert (
            attempt.failure_category
            == {
                "missing_location": FailureCategory.CONFIGURATION_ERROR,
                "provider_failure": FailureCategory.AUTHENTICATION_FAILED,
                "processing_failure": FailureCategory.INTERNAL_PROCESSING_ERROR,
            }[mode]
        )
    assert len(calls) == (0 if mode == "missing_location" else 1)
    assert schedule_before == [
        (s.id, s.status, s.next_scheduled_at, s.cron_expression, s.policy_version)
        for s in session.scalars(select(ScheduleDefinition))
    ]


def test_missing_market_blocks_preview_and_dispatch(session):
    tenant, site, run, service = queued_domain(session)
    cp = session.get(
        ProviderCapabilityPolicy, uuid.UUID(run.configuration_json["provider_capability_policy_id"])
    )
    cp.schedule_configuration_json = {"hour": 8}
    session.flush()
    request = ManualRequest(
        request_id=uuid.uuid4(),
        target_ids=[uuid.UUID(run.configuration_json["provider_target_id"])],
    )
    assert any("search market" in b for b in invoke(session, tenant, site, request)["blockers"])
    with pytest.raises(Exception, match="location/language") as error:
        execution_arguments(session, run, session.get(PipelineDefinition, run.pipeline_id))
    assert error.value.category == FailureCategory.CONFIGURATION_ERROR


def test_historical_success_with_failed_ingestion_is_read_only_effective_failure(session):
    tenant, site, run, _ = queued_domain(session)
    from gis.models import OrchestrationStatus, TriggerType

    ingestion = IngestionRun(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_connection_id=run.data_source_connection_id,
        started_at=run.available_at,
        status=IngestionStatus.FAILED,
        error_count=1,
        error_summary="ValueError: DataForSEO Labs requires a location target",
    )
    session.add(ingestion)
    session.flush()
    run.ingestion_run_id, run.status = ingestion.id, OrchestrationStatus.SUCCEEDED
    attempt = ExecutionAttempt(
        orchestration_run_id=run.id,
        attempt_number=1,
        trigger_type=TriggerType.MANUAL,
        worker_id="fixture-worker",
        started_at=run.available_at,
        status=OrchestrationStatus.SUCCEEDED,
        ingestion_run_id=ingestion.id,
    )
    session.add(attempt)
    session.flush()
    result = SystemQueries(session).run_summary(run)
    assert result["outcome"] == result["status"] == "FAILED"
    assert result["recorded_status"] == "SUCCEEDED"
    assert result["effective_failure_category"] == "CONFIGURATION_ERROR"
    assert result["provider_cost_exact"] is None
    assert result["attempt_timeline"][0]["effective_status"] == "FAILED"
    assert (
        SystemQueries(session).runs(tenant.id, site.id, status="FAILED", page=1, limit=20)["total"]
        == 1
    )
    assert (
        SystemQueries(session).runs(tenant.id, site.id, status="SUCCEEDED", page=1, limit=20)[
            "total"
        ]
        == 0
    )
    assert not session.dirty
    assert run.status.value == attempt.status.value == "SUCCEEDED"


def test_failed_cli_exit_and_exact_worker_ingestion_link(session, monkeypatch, capsys):
    from gis.integrations.external_search import cli
    from gis.orchestration import execution

    tenant, site, run, _ = queued_domain(session)
    ingestion = IngestionRun(
        tenant_id=tenant.id,
        site_id=site.id,
        data_source_connection_id=run.data_source_connection_id,
        started_at=run.available_at,
        status=IngestionStatus.FAILED,
        error_count=1,
        error_summary="Fixture processing failure",
    )
    session.add(ingestion)
    session.flush()
    monkeypatch.setattr(cli, "session_factory", lambda: lambda: nullcontext(session))
    monkeypatch.setattr(cli, "_credentials", lambda reference: ("fixture", "fixture"))
    monkeypatch.setattr(
        cli,
        "ExternalSearchCollector",
        lambda *args: SimpleNamespace(sync=lambda *args, **kwargs: ingestion),
    )
    assert (
        cli.run(
            [
                "keywords",
                "--connection",
                str(run.data_source_connection_id),
                "--site",
                str(site.id),
                "--domain",
                "vahomemath.com",
                "--location-code",
                "2840",
                "--language",
                "en",
            ]
        )
        == 1
    )
    stdout = capsys.readouterr().out
    assert json.loads(stdout)["ingestion_run_id"] == str(ingestion.id)
    monkeypatch.setattr(execution, "collector_environment", lambda *args: {})
    monkeypatch.setattr(
        execution.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=stdout, stderr=""),
    )
    result = execution.collector_cli_handler(session, run)
    assert result.ingestion_run_id == ingestion.id
    assert result.actual_cost is None


def test_errors_cannot_be_hidden_by_ingestion_success_status():
    from gis.orchestration.ingestion import ingestion_failure

    ingestion = IngestionRun(status=IngestionStatus.SUCCEEDED, error_count=1, source_metadata={})
    assert ingestion_failure(ingestion) is not None
