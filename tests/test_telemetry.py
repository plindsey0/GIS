from __future__ import annotations

import json
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import gis.api.app as api_module
from gis.api.app import app
from gis.models import (
    CalculatorRun,
    ConnectionStatus,
    ConnectionType,
    Conversion,
    DataRightsPolicy,
    DataSource,
    DataSourceConnection,
    Organization,
    ProductEvent,
    ProductSession,
    Site,
    Tenant,
)
from gis.seed import seed
from gis.telemetry.schemas import TelemetryBatchInput
from gis.telemetry.service import TelemetryService, resolve_context

NOW = datetime(2026, 8, 29, 15, tzinfo=timezone.utc)
SESSION_KEY = uuid.UUID("f6de9bc7-bf66-4bc8-b52f-b49ae16ed1b8")
VISITOR_KEY = uuid.UUID("150fa37e-5cd0-4506-a504-6e67ac8ce298")
RUN_KEY = uuid.UUID("a441087c-c2ea-44c9-b71c-b15d77bbef20")


def setup_connection(session: Session, monkeypatch: Any | None = None) -> DataSourceConnection:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    source = session.scalar(select(DataSource).where(DataSource.key == "first_party"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and source and site
    connection = session.scalar(
        select(DataSourceConnection).where(
            DataSourceConnection.tenant_id == tenant.id,
            DataSourceConnection.site_id == site.id,
            DataSourceConnection.data_source_id == source.id,
        )
    )
    if connection is None:
        connection = DataSourceConnection(
            tenant_id=tenant.id,
            site_id=site.id,
            data_source_id=source.id,
            connection_type=ConnectionType.CUSTOMER_SIDE,
            status=ConnectionStatus.ACTIVE,
            credential_reference="env:TELEMETRY_TEST_CREDENTIAL",
        )
        session.add(connection)
    session.commit()
    if monkeypatch is not None:
        monkeypatch.setenv("TELEMETRY_TEST_CREDENTIAL", json.dumps({"write_key": "test-secret"}))
        monkeypatch.setattr(api_module, "session_factory", lambda: lambda: nullcontext(session))
    return connection


def event(event_name: str, offset: int, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"telemetry:{event_name}:{offset}")),
        "event_name": event_name,
        "event_version": 1,
        "occurred_at": (NOW + timedelta(minutes=offset)).isoformat(),
        "page_path": "/va-loan-calculator/?email=not-stored",
        "properties": properties or {},
    }


def lifecycle_payload() -> dict[str, Any]:
    calculator_input = {
        "calculator_run_key": str(RUN_KEY),
        "calculator_type": "va_loan",
        "input_schema_version": "va_loan:v1",
        "home_price_bucket": "350k_400k",
        "loan_term": 30,
        "state_code": "WV",
        "funding_fee_exempt": True,
    }
    return {
        "tenant_key": "vahomemath",
        "site_key": "vahomemath",
        "session_key": str(SESSION_KEY),
        "anonymous_visitor_key": str(VISITOR_KEY),
        "landing_url": "https://vahomemath.test/va-loan-calculator/?gclid=secret",
        "referrer_url": "https://google.com/search?q=sensitive",
        "utm_source": "google",
        "utm_medium": "organic",
        "events": [
            event("page_view", 0, {"page_title": "VA Loan Calculator"}),
            event("calculator_start", 1, calculator_input),
            event("calculator_recalculate", 2, calculator_input),
            event(
                "calculator_complete",
                3,
                {
                    "calculator_run_key": str(RUN_KEY),
                    "calculator_type": "va_loan",
                    "result_schema_version": "va_loan_result:v1",
                    "monthly_payment_bucket": "2k_2250",
                },
            ),
            event("cta_click", 4, {"cta_id": "apply", "cta_location": "results"}),
            event(
                "lead_form_complete",
                5,
                {"form_id": "partner-lead", "calculator_run_key": str(RUN_KEY)},
            ),
        ],
    }


def test_complete_lifecycle_and_exact_retry_are_idempotent(session: Session) -> None:
    setup_connection(session)
    batch = TelemetryBatchInput.model_validate(lifecycle_payload())
    context = resolve_context(session, "vahomemath", "vahomemath")
    first = TelemetryService(session).ingest(batch, context, now=NOW + timedelta(hours=1))
    second = TelemetryService(session).ingest(batch, context, now=NOW + timedelta(hours=1))
    product_session = session.scalar(select(ProductSession))
    run = session.scalar(select(CalculatorRun))
    conversion = session.scalar(select(Conversion))
    assert (first.accepted, first.duplicates, first.rejected) == (6, 0, 0)
    assert (second.accepted, second.duplicates, second.rejected) == (0, 6, 0)
    assert session.scalar(select(func.count()).select_from(ProductSession)) == 1
    assert session.scalar(select(func.count()).select_from(ProductEvent)) == 6
    assert session.scalar(select(func.count()).select_from(CalculatorRun)) == 1
    assert session.scalar(select(func.count()).select_from(Conversion)) == 1
    assert product_session and product_session.anonymous_visitor_key == VISITOR_KEY
    assert product_session.landing_url == "https://vahomemath.test/va-loan-calculator/"
    assert product_session.referrer_url == "https://google.com/search"
    assert run and run.recalculation_count == 1 and run.completed_at is not None
    assert run.input_bucket_data["home_price_bucket"] == "350k_400k"
    assert conversion and conversion.source_event_id is not None
    assert conversion.calculator_run_id == run.id


def test_late_event_preserves_occurred_and_received_times(session: Session) -> None:
    setup_connection(session)
    payload = lifecycle_payload()
    payload["events"] = [event("page_view", -60, {"page_title": "Late"})]
    context = resolve_context(session, "vahomemath", "vahomemath")
    TelemetryService(session).ingest(
        TelemetryBatchInput.model_validate(payload), context, now=NOW + timedelta(hours=1)
    )
    stored = session.scalar(select(ProductEvent))
    assert stored and stored.occurred_at == NOW - timedelta(minutes=60)
    assert stored.received_at == NOW + timedelta(hours=1)


def test_unknown_sensitive_and_malformed_events_are_rejected_individually(session: Session) -> None:
    setup_connection(session)
    payload = lifecycle_payload()
    payload["events"] = [
        event("page_view", 0),
        event("unknown", 1),
        event("lead_form_complete", 2, {"form_id": "lead", "email": "private@test"}),
        event("calculator_start", 3, {"calculator_type": "va_loan"}),
    ]
    result = TelemetryService(session).ingest(
        TelemetryBatchInput.model_validate(payload),
        resolve_context(session, "vahomemath", "vahomemath"),
        now=NOW + timedelta(hours=1),
    )
    assert (result.accepted, result.rejected) == (1, 3)
    assert {item.code for item in result.errors} == {
        "UNKNOWN_EVENT",
        "PROHIBITED_PROPERTY",
        "INVALID_EVENT_PROPERTIES",
    }


def test_fully_rejected_batch_does_not_create_session(session: Session) -> None:
    setup_connection(session)
    payload = lifecycle_payload()
    payload["events"] = [event("unknown", 0)]
    result = TelemetryService(session).ingest(
        TelemetryBatchInput.model_validate(payload),
        resolve_context(session, "vahomemath", "vahomemath"),
        now=NOW + timedelta(hours=1),
    )
    assert (result.accepted, result.rejected) == (0, 1)
    assert session.scalar(select(func.count()).select_from(ProductSession)) == 0


def test_api_authentication_partial_batch_health_and_secrets(
    session: Session, monkeypatch: Any
) -> None:
    setup_connection(session, monkeypatch)
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/v1/telemetry/events", json=lifecycle_payload()).status_code == 401
    assert (
        client.post(
            "/v1/telemetry/events", headers={"X-Telemetry-Key": "wrong"}, json=lifecycle_payload()
        ).status_code
        == 403
    )
    payload = lifecycle_payload()
    payload["events"].append(event("unknown", 10))
    response = client.post(
        "/v1/telemetry/events",
        headers={"X-Telemetry-Key": "test-secret"},
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["accepted"] == 6
    assert response.json()["rejected"] == 1
    assert "test-secret" not in response.text


def test_api_limits_malformed_json_and_excessive_count(session: Session, monkeypatch: Any) -> None:
    setup_connection(session, monkeypatch)
    client = TestClient(app)
    headers = {"X-Telemetry-Key": "test-secret"}
    assert client.post("/v1/telemetry/events", headers=headers, content="{").status_code == 422
    assert (
        client.post("/v1/telemetry/events", headers=headers, content=b"x" * 70_000).status_code
        == 413
    )
    payload = lifecycle_payload()
    payload["events"] = [event("page_view", number) for number in range(51)]
    assert client.post("/v1/telemetry/events", headers=headers, json=payload).status_code == 422


def test_rights_override_is_applied(session: Session) -> None:
    connection = setup_connection(session)
    policy = DataRightsPolicy(tenant_id=connection.tenant_id, name="Telemetry override")
    session.add(policy)
    session.flush()
    connection.rights_policy_id = policy.id
    session.commit()
    payload = lifecycle_payload()
    payload["events"] = [event("page_view", 0)]
    TelemetryService(session).ingest(
        TelemetryBatchInput.model_validate(payload),
        resolve_context(session, "vahomemath", "vahomemath"),
        now=NOW + timedelta(hours=1),
    )
    stored = session.scalar(select(ProductEvent))
    assert stored and stored.rights_policy_id == policy.id


def test_database_rejects_connection_from_another_site(session: Session) -> None:
    connection = setup_connection(session)
    organization = session.scalar(select(Organization))
    assert organization is not None
    other_site = Site(
        tenant_id=connection.tenant_id,
        organization_id=organization.id,
        name="Other site",
        slug="other-site",
        canonical_url="https://other.test",
        timezone="UTC",
    )
    session.add(other_site)
    session.flush()
    source = session.get(DataSource, connection.data_source_id)
    assert source and source.default_rights_policy_id
    session.add(
        ProductSession(
            tenant_id=connection.tenant_id,
            site_id=other_site.id,
            data_source_connection_id=connection.id,
            rights_policy_id=source.default_rights_policy_id,
            session_key=uuid.uuid4(),
            started_at=NOW,
            last_event_at=NOW,
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()
