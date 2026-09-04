import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import requests
from sqlalchemy import func, select
from test_builtwith import configured
from test_workbench_api import client as api_client  # noqa: F401
from test_workbench_api import headers

from gis.api.system import SystemQueries
from gis.integrations.builtwith.telemetry import (
    TelemetryFailure,
    WhoAmIProvider,
    normalize,
    refresh,
    telemetry_status,
)
from gis.models import (
    DataRightsGrant,
    DataRightsPolicy,
    IngestionRun,
    PermittedUse,
    ProviderUsageEvent,
    TechnologyObservation,
)
from gis.provenance.review import (
    RightsReviewInput,
    required_rights,
    review_context,
    review_policy,
    scoped_connection,
)


def response():
    return {
        "account": {"email": "private@example.test", "key": "never-store"},
        "credits": {"purchased": 2000, "used": 1, "remaining": "1999.125"},
        "rate_limits": {"requests_per_second": 10, "concurrency": 8},
        "privacy": {
            "pii_allowed": False,
            "default_privacy_mode": "nopii",
            "flags_supported": ["NOPII", "never-store"],
        },
        "endpoints": {
            "operations": [
                {"id": "domain.lookup", "path": "/v23/api.json?KEY=never-store"},
                {"id": "domain.lookup", "path": "/v23/api.json"},
            ]
        },
    }


@pytest.mark.parametrize("state,blocked", [("UNKNOWN", True), ("DENIED", True), ("ALLOWED", False)])
def test_review_versions_and_least_privilege(session, state, blocked):
    tenant, site, connection, _ = configured(session)
    old = session.get(DataRightsPolicy, connection.rights_policy_id)
    context = review_context(session, connection)
    grants = {use.value: "UNKNOWN" for use in PermittedUse}
    grants.update(raw_retention=state, normalized_retention=state)
    payload = RightsReviewInput(
        expected_policy_id=old.id,
        review_authority="Fixture operator",
        documented_basis="Fixture reviewed contract",
        policy_version="review-2",
        effective_at=datetime.now(timezone.utc),
        decisions=context["decisions"],
        grants=grants,
    )
    new = review_policy(session, connection, payload)
    assert new.supersedes_policy_id == old.id and old.reviewed_at is None
    assert new.review_authority == "Fixture operator" and new.reviewed_at
    assert all(item["blocking"] is blocked for item in required_rights(session, connection))
    assert len(review_context(session, connection)["history"]) == 2
    assert session.scalar(
        select(func.count()).select_from(DataRightsGrant).where(DataRightsGrant.policy_id == new.id)
    ) == len(PermittedUse)
    with pytest.raises(ValueError, match="Policy changed"):
        review_policy(session, connection, payload)


def test_review_scope_rejects_other_site(session):
    import uuid

    tenant, _, connection, _ = configured(session)
    with pytest.raises(ValueError):
        scoped_connection(session, connection.id, tenant.id, uuid.uuid4())


def test_review_api_permissions_and_confirmation(api_client, session, monkeypatch):  # noqa: F811
    session.join_transaction_mode = "create_savepoint"
    tenant, site, connection, _ = configured(session)
    params = {"tenant_id": str(tenant.id), "site_id": str(site.id)}
    path = f"/api/v1/connections/{connection.id}"
    assert api_client.get(path + "/rights", params=params, headers=headers()).status_code == 200
    assert (
        api_client.post(
            path + "/rights/reviews", params=params, headers=headers(), json={}
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            path + "/account-telemetry/refresh",
            params=params,
            headers=headers(),
            json={"actor": "fixture", "confirmed": True},
        ).status_code
        == 403
    )
    response = api_client.post(
        path + "/account-telemetry/refresh",
        params=params,
        headers=headers("ADMIN"),
        json={"actor": "fixture", "confirmed": False},
    )
    assert response.status_code == 409
    monkeypatch.setenv("GIS_PAID_EXECUTION_DISABLED", "1")
    response = api_client.post(
        path + "/account-telemetry/refresh",
        params=params,
        headers=headers("ADMIN"),
        json={"actor": "fixture", "confirmed": True},
    )
    assert response.status_code == 409


def test_safe_account_snapshot_and_staleness(session, monkeypatch):
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    _, _, connection, _ = configured(session)
    counts = {
        model: session.scalar(select(func.count()).select_from(model))
        for model in (IngestionRun, ProviderUsageEvent, TechnologyObservation)
    }

    class HTTP:
        def get(self, url, **kwargs):
            assert "?" not in url and kwargs["allow_redirects"] is False
            assert kwargs["headers"]["Authorization"] == "API fixture-key"
            return SimpleNamespace(status_code=200, text=json.dumps(response()))

    row = refresh(session, connection, "fixture", WhoAmIProvider("fixture-key", HTTP()))
    assert row.normalized["credits_remaining"] == "1999.125"
    assert row.normalized["concurrency"] == "8" and row.normalized["domain_api_advertised"] is True
    assert "never-store" not in json.dumps(row.normalized) and "private@" not in json.dumps(
        row.normalized
    )
    assert telemetry_status(session, connection)["state"] == "CURRENT"
    assert (
        telemetry_status(session, connection, row.checked_at + timedelta(hours=25))["state"]
        == "STALE"
    )
    assert all(
        session.scalar(select(func.count()).select_from(model)) == count
        for model, count in counts.items()
    )
    with pytest.raises(ValueError, match="one minute"):
        refresh(session, connection, "fixture", WhoAmIProvider("fixture-key", HTTP()))


@pytest.mark.parametrize(
    "status,category",
    [
        (401, "AUTHENTICATION_FAILED"),
        (403, "AUTHORIZATION_FAILED"),
        (429, "RATE_LIMITED"),
        (500, "PROVIDER_ERROR"),
    ],
)
def test_account_http_failures_are_sanitized(status, category):
    class HTTP:
        def get(self, *args, **kwargs):
            return SimpleNamespace(status_code=status, text="never-store")

    with pytest.raises(TelemetryFailure, match=category) as error:
        WhoAmIProvider("secret", HTTP()).retrieve()
    assert "never-store" not in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"error": "secret"},
        {"credits": {"remaining": True}, "rate_limits": {}, "privacy": {}},
    ],
)
def test_malformed_telemetry(payload):
    with pytest.raises(TelemetryFailure):
        normalize(payload)


def test_timeout_unavailable_and_hold(session, monkeypatch):
    monkeypatch.delenv("GIS_PAID_EXECUTION_DISABLED", raising=False)
    _, _, connection, _ = configured(session)
    assert telemetry_status(session, connection)["state"] == "UNKNOWN"

    class HTTP:
        def get(self, *args, **kwargs):
            raise requests.Timeout("secret URL")

    refresh(session, connection, "fixture", WhoAmIProvider("secret", HTTP()))
    assert telemetry_status(session, connection)["state"] == "UNAVAILABLE"
    assert telemetry_status(session, connection)["failure_category"] == "TIMEOUT"
    monkeypatch.setenv("GIS_PAID_EXECUTION_DISABLED", "1")
    with pytest.raises(ValueError, match="hold"):
        refresh(session, connection, "fixture")


def test_dependency_resolves_schedule_connection_without_rewriting_pipeline(session):
    tenant, site, _, _ = configured(session)
    detail = SystemQueries(session).source_detail("builtwith", tenant.id, site.id)
    assert "builtwith_technology" in detail["impact"]["affected_pipelines"]
    assert not detail["impact"]["unmapped_dependencies"]
    assert "No materialized asset lineage" in detail["impact"]["explanation"]
    unresolved = SystemQueries(session).source_detail("semrush", tenant.id, site.id)
    assert unresolved["impact"]["unmapped_dependencies"]
    assert "cannot be determined" in unresolved["impact"]["explanation"]
