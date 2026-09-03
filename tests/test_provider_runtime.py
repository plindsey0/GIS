from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_provider_configuration import setup

from gis.integrations.serp.service import SerpCollector
from gis.models import (
    DataRightsPolicy,
    DataSourceConnection,
    ExecutionAttempt,
    ExecutorRole,
    FailureCategory,
    ObligationStatus,
    OrchestrationObligation,
    OrchestrationStatus,
    PipelineDefinition,
    ProviderUsageEvent,
    RightsDecision,
    ScheduleDefinition,
)
from gis.orchestration.execution import collector_environment
from gis.orchestration.service import Orchestrator, PipelineResult, Worker, record_heartbeat
from gis.provider_control.credentials import CredentialUnavailable, dataforseo_credentials
from gis.provider_control.recovery import recovery_preview
from gis.provider_control.runtime import readiness


def test_legacy_file_resolution_and_no_secret_errors(tmp_path: Path) -> None:
    file = tmp_path / "dataforseo.env"
    file.write_text("DATAFORSEO_LOGIN='fixture-login'\nDATAFORSEO_PASSWORD='fixture-password'\n")
    file.chmod(0o600)
    assert dataforseo_credentials(
        "env:GIS_DATAFORSEO_CREDENTIAL", environment={}, secret_file=file
    ) == ("fixture-login", "fixture-password")
    file.chmod(0o644)
    with pytest.raises(CredentialUnavailable) as failure:
        dataforseo_credentials("env:GIS_DATAFORSEO_CREDENTIAL", environment={}, secret_file=file)
    assert "fixture-password" not in str(failure.value)
    with pytest.raises(CredentialUnavailable):
        dataforseo_credentials("env:TEST_MISSING", environment={}, secret_file=file)
    with pytest.raises(CredentialUnavailable):
        dataforseo_credentials("env:TEST", environment={"TEST": "not-json"})


def test_credentials_resolve_in_real_child_process_without_authentication() -> None:
    env = {
        **os.environ,
        "GIS_TEST_RUNTIME": json.dumps({"login": "stub", "password": "not-a-secret"}),
    }
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gis.provider_control.credentials import probe; print(probe('env:GIS_TEST_RUNTIME')['state'])",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert child.stdout.strip() == "CONNECTED_AND_RESOLVABLE"
    assert "not-a-secret" not in child.stdout + child.stderr


def test_exact_missing_credential_then_recovered_late(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, query, config, service = setup(session)
    connection = session.get(DataSourceConnection, config.policy.data_source_connection_id)
    assert connection
    connection.credential_reference = "env:GIS_TEST_RUNTIME"
    rights = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Runtime fixture",
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        raw_storage_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
    )
    session.add(rights)
    session.flush()
    connection.rights_policy_id = rights.id
    config.activate = True
    config.policy.allow_unknown_cost = True
    config.capabilities[0].unit_price = None
    service.save(tenant.id, site.id, "dataforseo", config)
    schedule = session.scalar(
        select(ScheduleDefinition).where(ScheduleDefinition.tenant_id == tenant.id)
    )
    assert schedule
    due = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    schedule.next_scheduled_at = due
    run = Orchestrator(session).enqueue_due(due)[0]
    pipeline = session.get(PipelineDefinition, run.pipeline_id)
    assert pipeline
    calls = []

    class Stub:
        def collect(self, _query):
            calls.append("request")
            return {"tasks": [{"id": "stub-task", "result": []}]}

    def handler(db, execution):
        collector_environment(db, execution, pipeline)  # The real worker credential path.
        check = service.control.preflight(
            tenant.id,
            site.id,
            "dataforseo",
            "SERP_COLLECTION",
            [query.normalized_query],
            1,
            Decimal(1),
            reserve=True,
        )
        assert check.can_execute and check.reservation_id
        db.commit()
        ingestion = SerpCollector(db, Stub()).sync(connection.id, query)
        service.control.reconcile(
            check.reservation_id,
            actual_cost=None,
            semantics="UNKNOWN",
            status="SUCCEEDED",
            ingestion_run_id=ingestion.id,
        )
        return PipelineResult(ingestion_run_id=ingestion.id, actual_cost=None)

    monkeypatch.delenv("GIS_TEST_RUNTIME", raising=False)
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    worker = Worker(session, {pipeline.handler_key: handler}, "fixture-runtime-worker")
    worker.run_once(due)
    assert run.status == OrchestrationStatus.FAILED and calls == []
    attempt = session.scalar(
        select(ExecutionAttempt).where(ExecutionAttempt.orchestration_run_id == run.id)
    )
    assert attempt
    assert attempt.failure_category == FailureCategory.CONFIGURATION_ERROR
    assert attempt.error_classification == "CredentialUnavailable"
    assert "CREDENTIAL_UNAVAILABLE" in attempt.error_detail
    assert not recovery_preview(session, run)["can_retry"]
    assert not readiness(session, connection)["runnable"]
    original_error = attempt.error_detail
    monkeypatch.setenv(
        "GIS_TEST_RUNTIME", json.dumps({"login": "stub", "password": "not-a-secret"})
    )
    record_heartbeat(session, "fixture-runtime-worker", ExecutorRole.WORKER)
    assert readiness(session, connection)["worker_verified"]
    assert recovery_preview(session, run)["can_retry"]
    original_obligation = run.obligation_id
    Orchestrator(session).retry(tenant.id, run.id)
    worker.run_once(datetime.now(timezone.utc) + timedelta(minutes=2))
    assert run.obligation_id == original_obligation and run.status == OrchestrationStatus.SUCCEEDED
    obligation = session.get(OrchestrationObligation, original_obligation)
    assert obligation
    assert (
        obligation.status == ObligationStatus.SATISFIED
        and obligation.satisfied_at > obligation.due_at
    )
    attempts = list(
        session.scalars(
            select(ExecutionAttempt)
            .where(ExecutionAttempt.orchestration_run_id == run.id)
            .order_by(ExecutionAttempt.attempt_number)
        )
    )
    assert len(attempts) == 2 and attempts[0].error_detail == original_error
    assert calls == ["request"] and run.ingestion_run_id
    usage = session.scalar(
        select(ProviderUsageEvent).where(ProviderUsageEvent.tenant_id == tenant.id)
    )
    assert usage
    assert usage.request_count == 1 and usage.actual_cost is None and usage.estimated_cost is None
    detail = service.control.detail(tenant.id, site.id, "dataforseo")
    assert detail["request_count"] == 1
    assert detail["cost_state"] == "UNKNOWN_UNRECONCILED"
    assert detail["known_actual_cost_month"] is None
    from gis.api.system import SystemQueries

    assert (
        SystemQueries(session).pipeline_detail(pipeline.key, tenant.id, site.id)[
            "latest_obligation"
        ]["timeliness"]
        == "RECOVERED_LATE"
    )


@pytest.mark.parametrize(
    "message,category",
    [
        ('{"error":"referenced credential is unavailable"}', FailureCategory.CONFIGURATION_ERROR),
        ("401 authentication rejected", FailureCategory.AUTHENTICATION_FAILED),
        ("403 permission denied", FailureCategory.AUTHORIZATION_FAILED),
        ("503 provider unavailable", FailureCategory.PROVIDER_5XX),
        ("network error", FailureCategory.TRANSIENT_NETWORK),
        ("provider data pending", FailureCategory.PROVIDER_DATA_PENDING),
    ],
)
def test_collector_failure_classification(message: str, category: FailureCategory) -> None:
    from gis.orchestration.reliability import collector_failure

    assert collector_failure(message).category == category


def test_rate_limit_preserves_retry_after_without_leaking_output() -> None:
    from gis.orchestration.reliability import collector_failure

    error = collector_failure("429 Retry-After: 120 credential-payload-do-not-log")
    assert error.category == FailureCategory.PROVIDER_429
    assert error.retry_after_seconds == 120
    assert "credential-payload" not in str(error)


def test_candidate_provider_authorization_preserves_computed_monthly_plan(session: Session) -> None:
    from gis.collection_planning.service import CollectionPlanningService
    from gis.market_intelligence.service import MarketIntelligenceService
    from gis.models import (
        CollectionCadence,
        CollectionPlanItem,
        CollectionPlanningDecision,
        CollectionTargetStatus,
        CollectionTargetType,
        ProviderCollectionTarget,
        RightsStatus,
    )

    tenant, site, query, config, service = setup(session)
    service.save(tenant.id, site.id, "dataforseo", config)
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Candidate fixture",
        slug="candidate-fixture",
        tracked_query_ids=[query.id],
    )
    planning = CollectionPlanningService(session)
    target = planning.seed_target(
        market,
        CollectionTargetType.QUERY,
        "va funding fee calculator",
        "fixture",
        "canonical candidate",
    )
    planning.plan(market)
    decision = session.scalar(
        select(CollectionPlanningDecision).where(CollectionPlanningDecision.target_id == target.id)
    )
    assert decision
    target.human_managed = False
    target.status = decision.computed_status = CollectionTargetStatus.CANDIDATE
    decision.computed_cadence = CollectionCadence.MONTHLY
    plans = list(
        session.scalars(
            select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
        )
    )
    assert plans
    for item in plans:
        item.rights_status = RightsStatus.ALLOWED
    session.flush()
    choices = service.choices(tenant.id, site.id, "QUERY")
    candidate = next(c for c in choices if c["id"] == str(target.id))
    assert candidate["eligible"] and candidate["computed_cadence"] == "MONTHLY"
    before = (
        decision.computed_status,
        decision.computed_cadence,
        decision.priority_score,
        list(decision.blockers_json),
    )
    config.capabilities[0].target_ids = [target.id]
    config.policy.reason = "Operator wants weekly competitive coverage"
    service.save(tenant.id, site.id, "dataforseo", config)
    authorization = session.scalar(
        select(ProviderCollectionTarget).where(
            ProviderCollectionTarget.target_reference_id == target.id
        )
    )
    assert authorization and authorization.enabled
    assert authorization.metadata_json["computed_cadence"] == "MONTHLY"
    assert authorization.metadata_json["provider_cadence"] == "WEEKLY"
    assert authorization.metadata_json["execution_query_id"]
    assert not target.human_managed
    assert before == (
        decision.computed_status,
        decision.computed_cadence,
        decision.priority_score,
        list(decision.blockers_json),
    )
    config.capabilities[0].target_ids = []
    service.save(tenant.id, site.id, "dataforseo", config)
    assert (
        not authorization.enabled and authorization.metadata_json["reason"] == config.policy.reason
    )
