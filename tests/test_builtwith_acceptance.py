"""Isolated fixtures only: no provider network requests or production history."""

import io
import json
import uuid
from contextlib import nullcontext, redirect_stdout
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select
from test_builtwith import configured, payload

from gis.api.system import SystemQueries
from gis.integrations.builtwith import cli
from gis.integrations.builtwith.provider import BuiltWithProvider, provider_date
from gis.models import (
    ExecutionAttempt,
    IngestionRun,
    OrchestrationRun,
    ProviderPricingConfiguration,
    ProviderUsageEvent,
    TechnologyDetection,
    TechnologyObservation,
)
from gis.orchestration import execution
from gis.orchestration.service import Worker
from gis.provider_control.manual import ManualRequest, manual_run
from gis.provider_control.operations import provider_operations


@pytest.mark.parametrize("http_status", [200, 401, 429, "malformed", "processing"])
def test_real_cli_contract_through_worker(session, monkeypatch, http_status):
    session.join_transaction_mode = "create_savepoint"
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    monkeypatch.setenv("GIS_BUILTWITH_CREDENTIAL", "fixture-only-secret")
    tenant, site, connection, _ = configured(session)
    calls = []
    response = payload()
    tech = response["Results"][0]["Result"]["Paths"][0]["Technologies"][0]
    tech["FirstDetected"] = "2025-01-01T08:00:00-04:00"
    tech["LastDetected"] = "2026-09-03T12:00:00Z"

    class HTTP:
        def get(self, url, **kwargs):
            calls.append(kwargs["params"]["LOOKUP"])
            assert url == "https://api.builtwith.com/v23/api.json"
            assert kwargs["headers"]["Authorization"] == "API fixture-only-secret"
            assert "location_code" not in kwargs["params"]
            return SimpleNamespace(
                status_code=http_status if isinstance(http_status, int) else 200,
                text=json.dumps({} if http_status == "malformed" else response),
                headers={},
            )

    monkeypatch.setattr(cli, "session_factory", lambda: lambda: nullcontext(session))
    monkeypatch.setattr(
        cli, "BuiltWithProvider", lambda key: BuiltWithProvider(key, session=HTTP())
    )

    if http_status == "processing":
        from gis.integrations.builtwith import service

        def fail_processing(*args, **kwargs):
            raise ValueError("fixture-only-secret must not leak")

        monkeypatch.setattr(service, "resolve_provider_technology", fail_processing)

    def subprocess_fixture(arguments, **kwargs):
        output = io.StringIO()
        with redirect_stdout(output):
            code = cli.run(arguments[1:])
        assert "fixture-only-secret" not in output.getvalue()
        return SimpleNamespace(returncode=code, stdout=output.getvalue(), stderr="")

    monkeypatch.setattr(execution.subprocess, "run", subprocess_fixture)
    request = ManualRequest(request_id=uuid.uuid4())
    choices = manual_run(session, tenant.id, site.id, "builtwith", request)
    request.target_ids = [uuid.UUID(choices["choices"][0]["id"])]
    preview = manual_run(session, tenant.id, site.id, "builtwith", request)
    assert calls == []
    assert (preview["capabilities"], preview["targets"], preview["requests"]) == (1, 1, 1)
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    assert manual_run(session, tenant.id, site.id, "builtwith", request)["queued"] == 1
    queued = session.scalar(select(OrchestrationRun))
    result = Worker(
        session, {"COLLECTOR_CLI": execution.collector_cli_handler}, "fixture"
    ).run_once(queued.available_at + timedelta(seconds=1))
    attempt = session.scalar(select(ExecutionAttempt))
    ingestion = session.scalar(select(IngestionRun))
    usage = session.scalar(select(ProviderUsageEvent))
    assert (
        result.ingestion_run_id
        == attempt.ingestion_run_id
        == ingestion.id
        == usage.ingestion_run_id
    )
    assert calls == ["vahomemath.com"]
    assert usage.actual_cost is None
    assert usage.estimated_cost == Decimal("0.0495")
    if http_status == 200:
        assert result.status.value == ingestion.status.value == "SUCCEEDED"
        observation = session.scalar(select(TechnologyObservation))
        assert observation.ingestion_run_id == ingestion.id
        assert session.scalar(select(TechnologyDetection)).semantic_class == "PROVIDER_REPORTED"
        detection = session.scalar(select(TechnologyDetection))
        assert detection.provider_first_seen_at == provider_date(tech["FirstDetected"])
        assert detection.provider_last_seen_at == provider_date(tech["LastDetected"])
        assert observation.collection_metadata["payload"] == response
    else:
        assert result.status.value != "SUCCEEDED"
        assert ingestion.status.value == "FAILED"
        assert ingestion.source_metadata["failure_category"]
        assert "fixture-only-secret" not in ingestion.error_summary
        assert session.scalar(select(TechnologyObservation)) is None
    activity = provider_operations(session, connection.id, tenant.id, site.id)["activity"]
    assert len(activity) == 1
    assert activity[0]["capability_key"] == "TECHNOLOGY_PROFILE"
    detail = SystemQueries(session).run_detail(result.id, tenant.id, site.id)
    assert str(ingestion.id) in json.dumps(detail, default=str)


@pytest.mark.parametrize("value", [None, 1700000000, "invalid", "2026-09-03T12:00:00"])
def test_unknown_provider_dates_are_not_invented(value):
    assert provider_date(value) is None


def test_documented_provider_dates_normalize_to_utc():
    assert provider_date(1700000000000).isoformat() == "2023-11-14T22:13:20+00:00"
    assert provider_date("2026-09-03T08:00:00-04:00").isoformat() == "2026-09-03T12:00:00+00:00"


@pytest.mark.parametrize("allow_unknown", [False, True])
def test_unknown_cost_requires_explicit_bounded_policy(session, monkeypatch, allow_unknown):
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    tenant, site, _, service = configured(session)
    provider = service.control.provider("builtwith")
    session.execute(
        delete(ProviderPricingConfiguration).where(
            ProviderPricingConfiguration.provider_id == provider.id
        )
    )
    policy = service.control.policy(tenant.id, site.id, provider.id)
    policy.allow_unknown_cost = allow_unknown
    session.flush()
    preview = service.control.preflight(
        tenant.id, site.id, "builtwith", "TECHNOLOGY_PROFILE", ["vahomemath.com"], 1, Decimal(1)
    )
    assert preview.can_execute is allow_unknown
