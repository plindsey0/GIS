from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_collection_planning import scope as collection_scope
from test_opportunities import NOW, package

from gis.api.app import app
from gis.api.routes import database
from gis.collection_planning.service import CollectionPlanningService
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
from gis.orchestration.seed import seed_vahomemath_cadence
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


def test_provider_configuration_api_is_admin_only_and_preview_has_no_work(
    client: TestClient, session: Session
) -> None:
    from test_provider_configuration import setup

    tenant, site, _, config, _ = setup(session)
    query = params(tenant.id, site.id)
    url = "/api/v1/providers/dataforseo/configuration"
    body = config.model_dump(mode="json")
    assert client.get(url, params=query, headers=headers()).status_code == 200
    assert client.put(url, params=query, headers=headers(), json=body).status_code == 403
    assert (
        client.post(url + "/preview", params=query, headers=headers(), json=body).status_code == 403
    )
    preview = client.post(url + "/preview", params=query, headers=headers("ADMIN"), json=body)
    assert preview.status_code == 200 and preview.json()["paid_calls_made"] == 0
    saved = client.put(url, params=query, headers=headers("ADMIN"), json=body)
    assert saved.status_code == 200
    assert saved.json()["configuration"]["detail"]["collection_state"] == "CONNECTED_DISABLED"
    run = client.post(
        "/api/v1/providers/dataforseo/run",
        params=query,
        headers=headers(),
        json={"request_id": str(uuid.uuid4())},
    )
    assert run.status_code == 403
    recovery_url = f"/api/v1/providers/dataforseo/recover/{uuid.uuid4()}"
    assert (
        client.post(
            recovery_url, params=query, headers=headers(), json={"request_id": str(uuid.uuid4())}
        ).status_code
        == 403
    )
    missing = client.post(
        recovery_url, params=query, headers=headers("ADMIN"), json={"request_id": str(uuid.uuid4())}
    )
    assert missing.status_code == 409 and missing.json()["error"]["code"] == "RECOVERY_BLOCKED"


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


def test_goal_empty_create_detail_map_and_role_boundary(
    client: TestClient, session: Session
) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    query = params(tenant.id, site.id)
    empty = client.get("/api/v1/goals", params=query, headers=headers()).json()
    assert empty["items"] == [] and empty["summary"]["active_business_goals"] == 0
    denied = client.post(
        "/api/v1/goals",
        params=query,
        headers=headers("READ"),
        json={"name": "Operator goal", "objective_type": "GROWTH", "actor": "operator"},
    )
    assert denied.status_code == 403
    created = client.post(
        "/api/v1/goals",
        params=query,
        headers=headers("REVIEW"),
        json={"name": "Operator goal", "objective_type": "GROWTH", "actor": "operator"},
    )
    assert created.status_code == 201
    goal_id = created.json()["id"]
    assert created.json()["lifecycle"] == "DRAFT"
    detail = client.get(f"/api/v1/goals/{goal_id}", params=query, headers=headers()).json()
    assert detail["data"]["measurement_health"] == "NOT_YET_MEASURABLE"
    assert (
        client.get("/api/v1/goals/map", params=query, headers=headers()).json()["nodes"][0]["id"]
        == goal_id
    )
    isolated = client.get(
        f"/api/v1/goals/{goal_id}",
        params={"tenant_id": uuid.uuid4(), "site_id": site.id},
        headers=headers(),
    )
    assert isolated.status_code == 404


def test_goal_metric_recommendations_explain_measurement_choices(
    client: TestClient, session: Session
) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    response = client.get(
        "/api/v1/goals/metrics",
        params={**params(tenant.id, site.id), "goal_type": "GROWTH"},
        headers=headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["method"] == "DETERMINISTIC_POLICY"
    assert payload["recommended"][0]["recommendation_reason"]
    assert payload["recommended"][0]["source_name"] == "Google Analytics 4"


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
    assert overview["search"] == {
        "stored_observations": 0,
        "latest_observation": None,
        "rights_state": "UNKNOWN",
        "blocker": "No governed source observations are stored.",
        "clicks": None,
        "impressions": None,
        "ctr": None,
        "average_position": None,
        "observed_query_count": None,
    }
    assert overview["evidence"]["status"] == "NOT_PRODUCED"
    assert overview["collection_health"]["targets"] == 0
    assert (
        client.get("/api/v1/capabilities", params=scoped_params, headers=headers()).json()[
            "production_ai_operational"
        ]
        is False
    )


def test_capabilities_separate_source_and_automation_health(
    client: TestClient, session: Session
) -> None:
    seed(session, hostname="vahomemath.test")
    schedules = seed_vahomemath_cadence(session)
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site and schedules
    payload = client.get(
        "/api/v1/capabilities", params=params(tenant.id, site.id), headers=headers()
    ).json()
    assert payload["executor_liveness"] == {"SCHEDULER": False, "WORKER": False}
    item = payload["items"][0]
    assert set(item["source_health"]) >= {
        "state",
        "latest_ingestion_success",
        "latest_provider_reporting_date",
        "freshness_sla_seconds",
    }
    assert set(item["automation_health"]) >= {
        "state",
        "orchestration_run_count",
        "pending_obligations",
        "timeliness",
    }


def test_semantic_evidence_inventory_detail_and_diagnostics(
    client: TestClient, session: Session
) -> None:
    tenant, site, _ = scope(session)
    response = client.get(
        "/api/v1/evidence/packages",
        params={**params(tenant.id, site.id), "limit": 100},
        headers=headers(),
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["label"] and item["label"] != item["id"]
    assert item["status"] != "UNKNOWN"
    detail = client.get(
        f"/api/v1/evidence/packages/{item['id']}",
        params=params(tenant.id, site.id),
        headers=headers(),
    ).json()["data"]
    assert detail["label"] and "opportunity_evaluation" in detail
    diagnostics = client.get(
        "/api/v1/opportunity-evaluations",
        params=params(tenant.id, site.id),
        headers=headers(),
    ).json()
    assert diagnostics["evaluated"] >= 1
    assert diagnostics["items"][0]["closest"]["conditions"]
    assert diagnostics["diagnostics_materialization"] == "DERIVED_READ_MODEL"
    for path in (
        "/api/v1/opportunity-sufficiency/detectors",
        "/api/v1/opportunity-sufficiency/diagnose",
        "/api/v1/opportunity-sufficiency/collection-plan",
        "/api/v1/opportunity-sufficiency/portfolio",
    ):
        scoped = {} if path.endswith("detectors") else params(tenant.id, site.id)
        response = client.get(path, params=scoped, headers=headers())
        assert response.status_code == 200
    candidate_response = client.get(
        f"/api/v1/opportunity-sufficiency/candidates/{item['id']}",
        params=params(tenant.id, site.id),
        headers=headers(),
    )
    assert candidate_response.status_code == 200
    assert candidate_response.json()["recommendation_context"]["llm_invoked"] is False


def test_collection_pagination_filter_search_detail_and_isolation(
    client: TestClient, session: Session
) -> None:
    tenant, site, market = collection_scope(session)
    target = CollectionPlanningService(session).discover(market)[0]
    session.flush()
    response = client.get(
        "/api/v1/collection",
        params={
            **params(tenant.id, site.id),
            "target_type": "QUERY",
            "search": "loan calculator",
            "page": 1,
            "limit": 25,
            "sort": "name",
            "order": "asc",
        },
        headers=headers(),
    )
    assert response.status_code == 200 and response.json()["total"] == 1
    assert response.json()["items"][0]["status_explanation"]
    detail = client.get(
        f"/api/v1/collection/{target.id}",
        params=params(tenant.id, site.id),
        headers=headers(),
    )
    assert detail.status_code == 200 and detail.json()["label"] == target.display_value
    isolated = client.get(
        f"/api/v1/collection/{target.id}",
        params={"tenant_id": uuid.uuid4(), "site_id": site.id},
        headers=headers(),
    )
    assert isolated.status_code == 404


def test_system_pipeline_source_run_and_data_flow_views(
    client: TestClient, session: Session
) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    scoped_params = params(tenant.id, site.id)
    pipelines = client.get("/api/v1/system/pipelines", params=scoped_params, headers=headers())
    sources = client.get("/api/v1/system/sources", params=scoped_params, headers=headers())
    flow = client.get("/api/v1/system/data-flow", params=scoped_params, headers=headers())
    assert pipelines.status_code == sources.status_code == flow.status_code == 200
    assert sources.json()["items"][0]["label"]
    assert "methodology" in flow.json()
