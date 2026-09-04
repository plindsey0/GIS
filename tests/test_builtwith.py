import json
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from test_provider_control import scope

from gis.api.evidence_explorer import (
    domain_evidence_detail,
    source_options,
    technology_detection_detail,
    technology_domain_inventory,
)
from gis.api.system import SystemQueries
from gis.integrations.builtwith.cli import configure
from gis.integrations.builtwith.provider import BuiltWithProvider, parse_profile
from gis.integrations.builtwith.service import BuiltWithCollector
from gis.models import (
    DataRightsPolicy,
    Domain,
    ExecutionAttempt,
    FailureCategory,
    OrchestrationRun,
    ProviderCollectionTarget,
    ProviderUsageEvent,
    RightsDecision,
    ScheduleDefinition,
    TechnologyDetection,
    TechnologyEvidence,
    TechnologyObservation,
)
from gis.orchestration.reliability import ClassifiedFailure, collector_failure
from gis.orchestration.service import PipelineResult, Worker
from gis.provider_control.binding import execution_arguments
from gis.provider_control.configuration import CollectionConfiguration, ConfigurationService
from gis.provider_control.credentials import CredentialUnavailable, builtwith_credentials, probe
from gis.provider_control.manual import ManualRequest, manual_run
from gis.provider_control.operations import authentication, provider_operations


@pytest.mark.parametrize("lookup", [None, 123, [], "another.example"])
def test_malformed_lookup_is_provider_data_failure(lookup):
    response = payload()
    response["Results"][0]["Lookup"] = lookup
    with pytest.raises(ClassifiedFailure) as error:
        parse_profile(response, "vahomemath.com")
    assert error.value.category == FailureCategory.UNKNOWN_TERMINAL


def payload():
    return {
        "Results": [
            {
                "Lookup": "vahomemath.com",
                "Spend": 1234,
                "Result": {
                    "Paths": [
                        {
                            "Domain": "vahomemath.com",
                            "Url": "dd",
                            "Technologies": [
                                {
                                    "Id": 42,
                                    "Name": "Google Analytics 4",
                                    "Tag": "analytics",
                                    "Categories": ["Audience Measurement"],
                                    "FirstDetected": 1700000000000,
                                    "LastDetected": 1800000000000,
                                }
                            ],
                        }
                    ]
                },
            }
        ],
        "Errors": [],
    }


def configured(session):
    tenant, site, _ = scope(session)
    connection = configure(session, tenant.slug, site.slug, "env:GIS_BUILTWITH_CREDENTIAL")
    rights = session.get(DataRightsPolicy, connection.rights_policy_id)
    assert rights.raw_storage_allowed == RightsDecision.UNKNOWN
    assert rights.review_authority is None
    rights.raw_storage_allowed = rights.derived_storage_allowed = RightsDecision.ALLOWED
    domain = Domain(tenant_id=tenant.id, site_id=site.id, hostname="vahomemath.com")
    session.add(domain)
    session.flush()
    config = CollectionConfiguration.model_validate(
        {
            "policy": {
                "actor": "fixture-admin",
                "data_source_connection_id": str(connection.id),
                "monthly_hard_budget": "1",
                "per_run_hard_budget": "1",
                "daily_request_limit": 1,
                "monthly_request_limit": 5,
                "per_run_request_limit": 1,
                "allow_unknown_cost": True,
            },
            "capabilities": [
                {
                    "key": "TECHNOLOGY_PROFILE",
                    "enabled": True,
                    "cadence": "MANUAL_ONLY",
                    "target_ids": [str(domain.id)],
                    "unit_price": "0.0495",
                }
            ],
            "activate": True,
        }
    )
    service = ConfigurationService(session)
    service.save(tenant.id, site.id, "builtwith", config)
    return tenant, site, connection, service


def test_fixture_execution_links_full_control_plane_without_live_calls(session, monkeypatch):
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    monkeypatch.setenv("GIS_BUILTWITH_CREDENTIAL", "fixture-key")
    tenant, site, connection, service = configured(session)
    assert service.control.provider("builtwith").implementation_status == "IMPLEMENTED"
    request = ManualRequest(request_id=uuid.uuid4())
    options = manual_run(session, tenant.id, site.id, "builtwith", request)
    assert options["requests"] == 0 and len(options["choices"]) == 1
    assert not options["choices"][0]["default_selected"]
    request.target_ids = [uuid.UUID(options["choices"][0]["id"])]
    preview = manual_run(session, tenant.id, site.id, "builtwith", request)
    assert (preview["capabilities"], preview["targets"], preview["requests"]) == (1, 1, 1)
    assert Decimal(preview["estimated_cost"]) == Decimal("0.0495")
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    assert manual_run(session, tenant.id, site.id, "builtwith", request)["queued"] == 1
    assert manual_run(session, tenant.id, site.id, "builtwith", request)["queued"] == 0
    from gis.models import PipelineDefinition

    calls = []

    class Fixture:
        def collect(self, domain):
            calls.append(domain)
            return parse_profile(payload(), domain, {"x-api-credits-remaining": "99"})

    def handler(s, r):
        assert (
            execution_arguments(s, r, s.get(PipelineDefinition, r.pipeline_id))[-1]
            == "vahomemath.com"
        )
        assert builtwith_credentials(connection.credential_reference) == "fixture-key"
        ingestion = BuiltWithCollector(s, Fixture()).sync(connection.id, site.id, "vahomemath.com")
        return PipelineResult(ingestion_run_id=ingestion.id, actual_cost=None)

    queued = session.scalar(select(OrchestrationRun))
    result = Worker(session, {"COLLECTOR_CLI": handler}, "fixture-worker").run_once(
        queued.available_at + timedelta(seconds=1)
    )
    pipeline = session.get(PipelineDefinition, result.pipeline_id)
    summary = SystemQueries(session).run_summary(result, pipeline)
    assert summary["record_accounting_explanation"] is None
    assert result.status.value == "SUCCEEDED" and calls == ["vahomemath.com"]
    attempt = session.scalar(select(ExecutionAttempt))
    usage = session.scalar(select(ProviderUsageEvent))
    observation = session.scalar(select(TechnologyObservation))
    assert (
        attempt.ingestion_run_id
        == result.ingestion_run_id
        == usage.ingestion_run_id
        == observation.ingestion_run_id
    )
    assert (
        usage.request_count == 1
        and usage.actual_cost is None
        and usage.estimated_cost == Decimal("0.0495")
    )
    assert observation.collection_metadata["payload"] == payload()
    assert session.scalar(select(TechnologyEvidence)).evidence_value
    assert session.scalar(select(TechnologyDetection)).semantic_class == "PROVIDER_REPORTED"
    assert authentication(session, connection)["authentication_state"] == "VALIDATED"
    activity = provider_operations(session, connection.id, tenant.id, site.id)["activity"]
    assert (
        len(activity) == 1
        and activity[0]["request_count"] == 1
        and activity[0]["capability_key"] == "TECHNOLOGY_PROFILE"
    )
    assert all(s.next_scheduled_at is None for s in session.scalars(select(ScheduleDefinition)))
    # The next request exceeds the configured daily limit.
    assert not service.control.preflight(
        tenant.id, site.id, "builtwith", "TECHNOLOGY_PROFILE", ["vahomemath.com"], 1, Decimal(1)
    ).can_execute


def test_entity_centered_builtwith_evidence_is_read_only_and_rights_guarded(session, monkeypatch):
    """Two provider signatures may normalize to one canonical detection without data loss."""
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    tenant, site, connection, _ = configured(session)
    response = payload()
    duplicate_path = json.loads(json.dumps(response["Results"][0]["Result"]["Paths"][0]))
    duplicate_path["Url"] = "second-provider-path"
    response["Results"][0]["Result"]["Paths"].append(duplicate_path)

    class Fixture:
        def collect(self, domain):
            assert domain == "vahomemath.com"
            return parse_profile(
                response,
                domain,
                {
                    "x-api-credits-used": "1",
                    "x-api-credits-available": "2000",
                    "x-api-credits-remaining": "1999",
                },
            )

    run = BuiltWithCollector(session, Fixture()).sync(connection.id, site.id, "vahomemath.com")
    domain = session.scalar(
        select(Domain).where(
            Domain.tenant_id == tenant.id,
            Domain.site_id == site.id,
            Domain.hostname == "vahomemath.com",
        )
    )
    before = (
        session.query(TechnologyObservation).count(),
        session.query(TechnologyDetection).count(),
        session.query(TechnologyEvidence).count(),
    )
    inventory = technology_domain_inventory(
        session, tenant.id, site.id, page=1, limit=25, search="vahomemath"
    )
    detail = domain_evidence_detail(session, domain.id, tenant.id, site.id)
    assert inventory["total"] == 1
    assert inventory["items"][0]["entity_type"] == "DOMAIN"
    assert inventory["items"][0]["evidence_type"] == "TECHNOLOGY_PROFILE"
    assert detail["summary"]["canonical_subject"] == domain.hostname
    assert detail["technology_profile"]["detections"][0]["technology_name"] == "Google Analytics 4"
    assert detail["collection_accounting"]["records_received"] == 2
    assert detail["collection_accounting"]["normalized_detections_inserted"] == 1
    assert "both distinct source signatures" in detail["collection_accounting"]["explanation"]
    assert detail["cost_and_credits"] == {
        "provider_requests": 1,
        "provider_reported_credits_consumed": "1",
        "provider_reported_credits_remaining": "1999",
        "provider_reported_credits_available": "2000",
        "estimated_economic_cost": "0.04950000",
        "estimated_cost_currency": "USD",
        "actual_provider_usd_charge": None,
        "actual_cost_semantics": "NOT_REPORTED",
    }
    detection_id = uuid.UUID(detail["technology_profile"]["detections"][0]["id"])
    protected = technology_detection_detail(session, detection_id, tenant.id, site.id)
    assert protected["raw_display"]["status"] == "WITHHELD"
    assert "raw_provider_evidence" not in protected
    rights = session.get(DataRightsPolicy, run.rights_policy_id)
    rights.raw_display_allowed = RightsDecision.ALLOWED
    session.flush()
    permitted = technology_detection_detail(session, detection_id, tenant.id, site.id)
    assert permitted["raw_display"]["status"] == "ALLOWED"
    assert len(permitted["raw_provider_evidence"]) == 2
    assert any(option["value"] == "builtwith" for option in source_options(session))
    after = (
        session.query(TechnologyObservation).count(),
        session.query(TechnologyDetection).count(),
        session.query(TechnologyEvidence).count(),
    )
    assert after == before


def test_credentials_and_safe_failures(tmp_path, monkeypatch):
    secret = tmp_path / "builtwith.env"
    secret.write_text("GIS_BUILTWITH_CREDENTIAL=fixture-key\n")
    secret.chmod(0o600)
    assert (
        builtwith_credentials("env:GIS_BUILTWITH_CREDENTIAL", environment={}, secret_file=secret)
        == "fixture-key"
    )
    secret.chmod(0o644)
    with pytest.raises(CredentialUnavailable):
        builtwith_credentials("env:GIS_BUILTWITH_CREDENTIAL", environment={}, secret_file=secret)
    with pytest.raises(CredentialUnavailable) as caught:
        builtwith_credentials("env:MISSING_FIXTURE", environment={})
    assert caught.value.category == FailureCategory.CONFIGURATION_ERROR
    monkeypatch.setenv("GIS_BUILTWITH_CREDENTIAL", '{"api_key":"fixture-key"}')
    assert probe("env:GIS_BUILTWITH_CREDENTIAL", "builtwith")["state"] == "CONNECTED_AND_RESOLVABLE"


@pytest.mark.parametrize(
    "code,category",
    [
        (-2, FailureCategory.AUTHENTICATION_FAILED),
        (-3, FailureCategory.BUDGET_BLOCKED),
        (-99, FailureCategory.PROVIDER_5XX),
    ],
)
def test_provider_errors(code, category):
    with pytest.raises(ClassifiedFailure) as caught:
        parse_profile(
            {"Errors": [{"Code": code, "Message": "never persist secret text"}]}, "vahomemath.com"
        )
    assert caught.value.category == category and "secret" not in str(caught.value)
    classified = collector_failure(
        json.dumps({"failure_category": category.value, "error": "safe error"})
    )
    assert classified.category == category


def test_http_single_request_header_auth_no_redirect_no_spend_as_cost():
    class Response:
        status_code = 200
        text = json.dumps(payload())
        headers = {"X-API-CREDITS-REMAINING": "1"}

    class HTTP:
        def get(self, url, **kwargs):
            assert kwargs["params"]["LOOKUP"] == "vahomemath.com"
            assert "KEY" not in kwargs["params"] and kwargs["allow_redirects"] is False
            assert kwargs["headers"]["Authorization"] == "API fixture-key"
            return Response()

    result = BuiltWithProvider("fixture-key", session=HTTP()).collect("vahomemath.com")
    assert len(result.technologies) == 1 and result.payload["Results"][0]["Spend"] == 1234


@pytest.mark.parametrize("change", ["disabled", "unauthorized", "rights", "budget", "paused"])
def test_manual_controls(session, change):
    tenant, site, connection, service = configured(session)
    target = session.scalar(select(ProviderCollectionTarget))
    policy = service.control.policy(tenant.id, site.id, service.control.provider("builtwith").id)
    request = ManualRequest(request_id=uuid.uuid4(), target_ids=[target.id])
    if change == "disabled":
        from gis.models import ProviderCapabilityPolicy

        session.get(ProviderCapabilityPolicy, target.capability_policy_id).enabled = False
    elif change == "unauthorized":
        request.target_ids = [uuid.uuid4()]
    elif change == "rights":
        session.get(
            DataRightsPolicy, connection.rights_policy_id
        ).raw_storage_allowed = RightsDecision.UNKNOWN
    elif change == "budget":
        policy.per_run_hard_budget = Decimal("0.001")
    else:
        policy.status = "PAUSED"
    preview = manual_run(session, tenant.id, site.id, "builtwith", request)
    assert preview["blockers"]
    request.confirmed, request.fingerprint = True, preview["fingerprint"]
    with pytest.raises(ValueError):
        manual_run(session, tenant.id, site.id, "builtwith", request)
