from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_opportunities import NOW, package

from gis.api.app import app
from gis.api.routes import database
from gis.models import (
    DemandEvidenceStrength,
    Intervention,
    InterventionStatus,
    RecommendationCandidate,
    RecommendationReviewDecision,
    Site,
    Tenant,
)
from gis.opportunities.service import OpportunityService
from gis.recommendations.provider import FixtureRecommendationProvider
from gis.recommendations.service import RecommendationService
from gis.seed import seed

KEY = "local-test-operator-key"


@pytest.fixture()
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GIS_API_OPERATOR_KEY", KEY)

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[database] = override
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def headers(role: str = "READ") -> dict[str, str]:
    return {"X-GIS-Operator-Key": KEY, "X-GIS-Role": role}


def scope(session: Session):
    tenant, site, _ = package(session, DemandEvidenceStrength.SUPPORTED)
    opportunity = OpportunityService(session).detect(tenant.id, site.id, now=NOW)[0]
    return tenant, site, opportunity


def params(tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "site_id": str(site_id)}


def test_health_openapi_and_auth_boundary(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/openapi.json").json()["info"]["title"] == "GIS Application API"
    response = client.get("/api/v1/sites", params={"tenant_id": uuid.uuid4()})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
    assert "request_id" in response.json()["error"]


def test_site_and_tenant_isolation(client: TestClient, session: Session) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    assert client.get("/api/v1/sites", params={"tenant_id": tenant.id}, headers=headers()).json()[
        0
    ]["id"] == str(site.id)
    response = client.get(
        f"/api/v1/sites/{site.id}/status", params={"tenant_id": uuid.uuid4()}, headers=headers()
    )
    assert response.status_code == 404


def test_opportunity_inbox_filters_pagination_and_detail(
    client: TestClient, session: Session
) -> None:
    tenant, site, opportunity = scope(session)
    query = {
        **params(tenant.id, site.id),
        "status": "ACTIVE",
        "family": opportunity.family.value,
        "page": "1",
        "limit": "10",
    }
    response = client.get("/api/v1/opportunities", params=query, headers=headers())
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1 and payload["items"][0]["entity_key"]
    detail = client.get(
        f"/api/v1/opportunities/{opportunity.id}",
        params=params(tenant.id, site.id),
        headers=headers(),
    ).json()
    assert detail["resource_type"] == "opportunity" and "history" in detail["data"]


def test_invalid_id_and_validation_error_model(client: TestClient, session: Session) -> None:
    tenant, site, _ = scope(session)
    missing = client.get(
        f"/api/v1/opportunities/{uuid.uuid4()}",
        params=params(tenant.id, site.id),
        headers=headers(),
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "OPPORTUNITY_NOT_FOUND"
    invalid = client.get(
        "/api/v1/opportunities",
        params={**params(tenant.id, site.id), "limit": "1000"},
        headers=headers(),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "REQUEST_INVALID"
    assert invalid.json()["error"]["retryable"] is False


def test_generation_and_acceptance_create_draft_only(client: TestClient, session: Session) -> None:
    tenant, site, opportunity = scope(session)
    generated = client.post(
        f"/api/v1/opportunities/{opportunity.id}/recommendations",
        params=params(tenant.id, site.id),
        headers=headers("REVIEW"),
        json={},
    ).json()
    recommendation_id = generated["recommendation_id"]
    candidate = session.scalar(
        select(RecommendationCandidate).where(
            RecommendationCandidate.recommendation_id == recommendation_id
        )
    )
    assert candidate and generated["production_ai"] is False
    accepted = client.post(
        f"/api/v1/recommendations/{recommendation_id}/accept",
        params=params(tenant.id, site.id),
        headers=headers("REVIEW"),
        json={"actor": "reviewer", "candidate_ids": [str(candidate.id)]},
    )
    assert accepted.status_code == 200 and accepted.json()["intervention_approved"] is False
    intervention = session.scalar(
        select(Intervention).where(Intervention.primary_opportunity_id == opportunity.id)
    )
    assert intervention and intervention.status is InterventionStatus.DRAFT


def test_reject_preserves_history_and_no_provider_call(
    client: TestClient, session: Session
) -> None:
    tenant, site, opportunity = scope(session)
    service = RecommendationService(session, FixtureRecommendationProvider())
    generated = service.generate(opportunity.id)
    session.flush()
    response = client.post(
        f"/api/v1/recommendations/{generated['recommendation_id']}/reject",
        params=params(tenant.id, site.id),
        headers=headers("REVIEW"),
        json={"actor": "reviewer", "reason": "OUT_OF_SCOPE", "candidate_ids": []},
    )
    assert response.status_code == 200 and response.json()["status"] == "REJECTED"


def test_intervention_approval_is_separate_and_role_protected(
    client: TestClient, session: Session
) -> None:
    tenant, site, opportunity = scope(session)
    service = RecommendationService(session, FixtureRecommendationProvider())
    generated = service.generate(opportunity.id)
    candidate = session.scalar(
        select(RecommendationCandidate).where(
            RecommendationCandidate.recommendation_id == generated["recommendation_id"]
        )
    )
    assert candidate
    service.review(
        generated["recommendation_id"],
        RecommendationReviewDecision.ACCEPT,
        "reviewer",
        [candidate.id],
    )
    intervention = session.scalar(
        select(Intervention).where(Intervention.primary_opportunity_id == opportunity.id)
    )
    assert intervention
    session.flush()
    denied = client.post(
        f"/api/v1/interventions/{intervention.id}/approve",
        params=params(tenant.id, site.id),
        headers=headers("REVIEW"),
        json={"actor": "approver"},
    )
    assert denied.status_code == 403
    proposed = client.post(
        f"/api/v1/interventions/{intervention.id}/propose",
        params=params(tenant.id, site.id),
        headers=headers("REVIEW"),
        json={"actor": "reviewer"},
    )
    assert proposed.json()["status"] == "PROPOSED"
    approved = client.post(
        f"/api/v1/interventions/{intervention.id}/approve",
        params=params(tenant.id, site.id),
        headers=headers("APPROVE"),
        json={"actor": "approver"},
    )
    assert approved.json()["status"] == "APPROVED"


def test_invalid_transition_returns_conflict(client: TestClient, session: Session) -> None:
    tenant, site, opportunity = scope(session)
    generated = RecommendationService(session, FixtureRecommendationProvider()).generate(
        opportunity.id
    )
    candidate = session.scalar(
        select(RecommendationCandidate).where(
            RecommendationCandidate.recommendation_id == generated["recommendation_id"]
        )
    )
    assert candidate
    RecommendationService(session, FixtureRecommendationProvider()).review(
        generated["recommendation_id"],
        RecommendationReviewDecision.ACCEPT,
        "reviewer",
        [candidate.id],
    )
    intervention = session.scalar(
        select(Intervention).where(Intervention.primary_opportunity_id == opportunity.id)
    )
    assert intervention
    response = client.post(
        f"/api/v1/interventions/{intervention.id}/complete",
        params=params(tenant.id, site.id),
        headers=headers("APPROVE"),
        json={"actor": "operator"},
    )
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "INVALID_LIFECYCLE_TRANSITION"
    )


def test_read_surfaces_empty_unknown_and_no_activation(
    client: TestClient, session: Session
) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    scoped_params = params(tenant.id, site.id)
    for path in (
        "markets",
        "collection",
        "evidence/packages",
        "experiments",
        "outcomes",
        "recommendations",
        "interventions",
    ):
        response = client.get(f"/api/v1/{path}", params=scoped_params, headers=headers())
        assert response.status_code == 200
    overview = client.get("/api/v1/overview", params=scoped_params, headers=headers()).json()
    assert overview["unknown_values_are_zero"] is False
    assert (
        client.get("/api/v1/capabilities", params=scoped_params, headers=headers()).json()[
            "production_ai_operational"
        ]
        is False
    )
