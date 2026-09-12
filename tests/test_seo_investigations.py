from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_exact_query_serp_intelligence import scope
from test_query_page_intent import response

from gis.api.app import app
from gis.api.routes import database, router
from gis.evidence_gap_adjudication.service import EvidenceGapAdjudicationService
from gis.evidence_quality.service import EvidenceQualityService
from gis.intelligence.provider import ReplayLLMProvider
from gis.models import (
    AnalyticalEntityType,
    CollectionPriorityTier,
    DemandEvidenceStrength,
    EvidenceCompatibility,
    EvidencePackage,
    EvidencePackageItem,
    Intervention,
    QueryPageIntentReview,
    RightsUsability,
    SEOInvestigation,
    SEOInvestigationEvent,
    SourceIndependenceState,
)
from gis.query_page_intent.service import (
    GovernedReference,
    QueryPageIntentContext,
    QueryPageIntentService,
)
from gis.seo_investigations.service import SEOInvestigationError, SEOInvestigationService

QUERY = "va down payment calculator"
URL = "https://www.vahomemath.com/va-entitlement-calculator/"
KEY = "epic-29a-test-key"


@pytest.fixture()
def client(session: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("GIS_API_OPERATOR_KEY", KEY)

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[database] = override
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def params(tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, str]:
    return {"tenant_id": str(tenant_id), "site_id": str(site_id)}


def headers(role: str = "READ") -> dict[str, str]:
    return {"X-GIS-Operator-Key": KEY, "X-GIS-Role": role}


def investigation_scope(session: Session):  # type: ignore[no-untyped-def]
    tenant, site, _, _, market, _, query_entity, gap = scope(session)
    governing_package = session.get_one(EvidencePackage, gap.evidence_package_id)
    governing_package.analytical_entity_id = query_entity.id
    governing_package.market_definition_id = market.id
    page_entity = EvidenceQualityService(session).entity(
        tenant.id, site.id, AnalyticalEntityType.URL, URL,
        source_reference_type="governed_candidate_url", source_reference_id=uuid.uuid4())
    service = SEOInvestigationService(session)
    row = service.create(
        tenant_id=tenant.id, site_id=site.id, query_entity_id=query_entity.id,
        candidate_page_entity_id=page_entity.id, market_definition_id=market.id,
        exact_query=QUERY, candidate_url=URL,
        title="VA down payment calculator intent investigation",
        question="Does the VA Entitlement Calculator adequately target and satisfy the exact query?",
        priority=CollectionPriorityTier.HIGH, actor="operator")
    return tenant, site, market, query_entity, page_entity, gap, row, service


def test_create_is_idempotent_missing_evidence_has_safe_action_and_reads_have_no_effects(
    session: Session,
) -> None:
    tenant, site, market, query, page, _, row, service = investigation_scope(session)
    replay = service.create(
        tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
        candidate_page_entity_id=page.id, market_definition_id=market.id,
        exact_query=QUERY, candidate_url=URL, title="Ignored replay title",
        question="Ignored replay question", priority=CollectionPriorityTier.LOW,
        actor="operator")
    events_before = session.scalar(select(func.count()).select_from(SEOInvestigationEvent))
    interventions_before = session.scalar(select(func.count()).select_from(Intervention))
    detail = service.read_model(row)
    queue = service.action_queue(tenant.id, site.id)

    assert replay.id == row.id
    assert detail["stage"] == "AWAITING_ADJUDICATION"
    assert detail["query_page_intent"]["status"] == "NOT_INTERPRETED"
    assert detail["recommendation_eligible"] is False
    assert queue[0]["action_type"] == "RUN_GAP_ADJUDICATION"
    assert session.scalar(select(func.count()).select_from(SEOInvestigationEvent)) == events_before
    assert session.scalar(select(func.count()).select_from(Intervention)) == interventions_before


def test_scope_identity_market_and_readiness_bypass_fail_closed(session: Session) -> None:
    tenant, site, market, query, page, _, row, service = investigation_scope(session)
    with pytest.raises(SEOInvestigationError, match="query identity"):
        service.create(tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
            candidate_page_entity_id=page.id, market_definition_id=market.id,
            exact_query="related query", candidate_url=URL, title="Wrong", question="Wrong",
            priority=CollectionPriorityTier.HIGH, actor="operator")
    with pytest.raises(SEOInvestigationError, match="page identity"):
        service.create(tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
            candidate_page_entity_id=page.id, market_definition_id=market.id,
            exact_query=QUERY, candidate_url="https://www.vahomemath.com/other/",
            title="Wrong", question="Wrong", priority=CollectionPriorityTier.HIGH,
            actor="operator")
    with pytest.raises(SEOInvestigationError, match="absolute HTTP"):
        service.create(tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
            candidate_page_entity_id=page.id, market_definition_id=market.id,
            exact_query=QUERY, candidate_url="not-a-url", title="Wrong", question="Wrong",
            priority=CollectionPriorityTier.HIGH, actor="operator")
    with pytest.raises(SEOInvestigationError, match="Market definition"):
        service.create(tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
            candidate_page_entity_id=page.id, market_definition_id=uuid.uuid4(),
            exact_query=QUERY, candidate_url=URL, title="Wrong", question="Wrong",
            priority=CollectionPriorityTier.HIGH, actor="operator")
    for field, value, message in (
        ("country_code", "CA", "country"),
        ("language_code", "fr", "language"),
        ("device", "mobile", "device"),
    ):
        original = getattr(query, field)
        setattr(query, field, value)
        with pytest.raises(SEOInvestigationError, match=message):
            service.create(tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
                candidate_page_entity_id=page.id, market_definition_id=market.id,
                exact_query=QUERY, candidate_url=URL, title="Wrong", question="Wrong",
                priority=CollectionPriorityTier.HIGH, actor="operator")
        setattr(query, field, original)
    with pytest.raises(SEOInvestigationError, match="gates"):
        service.apply(row, "MARK_READY_FOR_RECOMMENDATION", "operator", "Too early")
    with pytest.raises(SEOInvestigationError, match="tenant/site"):
        service.scoped(row.id, uuid.uuid4(), site.id)


def test_owned_or_limited_evidence_does_not_overstate_intent_and_conflicts_are_visible(
    session: Session,
) -> None:
    tenant, site, _, _, _, gap, row, service = investigation_scope(session)
    package = session.get_one(EvidencePackage, gap.evidence_package_id)
    session.add(EvidencePackageItem(
        evidence_package_id=package.id, evidence_key="owned:page",
        evidence_type="CONTENT_OBSERVATION", evidence_role="SUPPORTING",
        root_source_key="owned_fixture", independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE, supports_claim=True,
        metadata_json={"url": URL}))
    package.sufficiency = DemandEvidenceStrength.LIMITED
    session.flush()
    partial = EvidenceGapAdjudicationService(session).adjudicate(
        gap.id, tenant_id=tenant.id, site_id=site.id, evidence_package_ids=[package.id])
    assert partial.outcome == "STILL_INSUFFICIENT"
    detail = service.read_model(row)
    assert detail["stage"] == "EVIDENCE_REQUIRED"
    assert detail["query_page_intent"]["status"] == "NOT_INTERPRETED"

    package.sufficiency = DemandEvidenceStrength.SUPPORTED
    package.conflict_count = 1
    session.add(EvidencePackageItem(
        evidence_package_id=package.id, evidence_key="serp:conflicting",
        evidence_type="EXACT_QUERY_SERP_SNAPSHOT", evidence_role="PRIMARY",
        root_source_key="serp_fixture", independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE, supports_claim=True,
        metadata_json={"query": QUERY}))
    session.flush()
    conflict = EvidenceGapAdjudicationService(session).adjudicate(
        gap.id, tenant_id=tenant.id, site_id=site.id, evidence_package_ids=[package.id])
    assert conflict.outcome == "CONFLICTING_EVIDENCE"
    detail = service.read_model(row)
    assert detail["stage"] == "CONFLICTING_EVIDENCE"
    assert detail["next_action"]["action_type"] == "REVIEW_CONFLICTING_EVIDENCE"
    assert detail["recommendation_eligible"] is False


def test_satisfied_evidence_and_review_advance_only_after_explicit_mark(session: Session) -> None:
    tenant, site, market, query, page, gap, row, service = investigation_scope(session)
    package = session.get_one(EvidencePackage, gap.evidence_package_id)
    session.add(EvidencePackageItem(
        evidence_package_id=package.id, evidence_key="serp:exact-query",
        evidence_type="EXACT_QUERY_SERP_SNAPSHOT", evidence_role="PRIMARY",
        root_source_key="fixture_serp", independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE, supports_claim=True,
        metadata_json={"query": QUERY, "country_code": "US", "language_code": "en", "device": "desktop"}))
    session.flush()
    adjudication = EvidenceGapAdjudicationService(session).adjudicate(
        gap.id, tenant_id=tenant.id, site_id=site.id, evidence_package_ids=[package.id])
    assert adjudication.outcome == "SATISFIED"
    context = QueryPageIntentContext(
        tenant_id=tenant.id, site_id=site.id, query_entity_id=query.id,
        page_entity_id=page.id, market_definition_id=market.id,
        exact_query=QUERY, candidate_url=URL,
        references=[GovernedReference(reference_id=uuid.uuid4(),
            reference_type="SERP_RESULT", evidence_package_ids=[package.id],
            exact_query=QUERY, page_url=URL, market_definition_id=market.id,
            root_source="fixture_serp")],
        page_content_claims=["A governed calculator page observation exists."],
        serp_claims=["Calculator results are observed for the exact query."],
        page_content_fingerprint="page-v1", serp_fingerprint="serp-v1",
        quality={"freshness": "SUPPORTED"})
    payload = response(context)
    payload["candidate_url"] = URL
    provider = ReplayLLMProvider({"query_page_intent_resolution": payload})
    assessment = QueryPageIntentService(session, provider).resolve(context)
    assert service.read_model(row)["stage"] == "AWAITING_HUMAN_REVIEW"
    session.add(QueryPageIntentReview(assessment_id=assessment.id, decision="CONFIRM",
        reviewer="operator", comment="Reviewed bounded evidence.", reviewed_at=assessment.evaluated_at))
    session.flush()
    ready = service.read_model(row)
    assert ready["stage"] == "READY_FOR_INTERPRETATION"
    assert ready["recommendation_eligible"] is False
    service.apply(row, "MARK_READY_FOR_RECOMMENDATION", "operator",
                  "All governed gates passed and review is complete.")
    assert service.read_model(row)["recommendation_eligible"] is True
    assert len(provider.calls) == 1 and provider.external is False
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_close_reopen_history_and_deterministic_filters(session: Session) -> None:
    tenant, site, _, _, _, _, row, service = investigation_scope(session)
    service.apply(row, "CLOSE_NO_ACTION", "operator", "No action is justified.")
    assert service.read_model(row)["stage"] == "CLOSED_NO_ACTION"
    service.apply(row, "REOPEN", "reviewer", "New governed evidence is expected.")
    history = service.read_model(row)["history"]
    assert [item["event_type"] for item in history] == ["CREATED", "CLOSE_NO_ACTION", "REOPEN"]
    assert len(service.inventory(tenant.id, site.id, priority="HIGH")) == 1
    assert service.inventory(tenant.id, site.id, stage="CLOSED_NO_ACTION") == []
    assert session.scalar(select(func.count()).select_from(SEOInvestigation)) == 1


def test_api_contract_is_registered() -> None:
    paths = {route.path for route in router.routes}
    assert {"/api/v1/seo-investigations", "/api/v1/seo-investigations/action-queue",
            "/api/v1/seo-investigations/{resource_id}",
            "/api/v1/seo-investigations/{resource_id}/actions",
            "/api/v1/seo-investigations/{resource_id}/history"} <= paths


def test_api_reads_are_scoped_and_lifecycle_actions_are_explicit(
    client: TestClient, session: Session,
) -> None:
    tenant, site, _, _, _, _, row, _ = investigation_scope(session)
    session.commit()
    query = params(tenant.id, site.id)

    listing = client.get("/api/v1/seo-investigations", params=query, headers=headers())
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == str(row.id)
    detail = client.get(
        f"/api/v1/seo-investigations/{row.id}", params=query, headers=headers()
    )
    assert detail.status_code == 200
    assert detail.json()["scope"]["exact_query"] == QUERY
    assert client.get(
        f"/api/v1/seo-investigations/{row.id}",
        params=params(uuid.uuid4(), site.id), headers=headers(),
    ).status_code == 404

    close = client.post(
        f"/api/v1/seo-investigations/{row.id}/actions", params=query,
        headers=headers("REVIEW"),
        json={"action": "CLOSE_NO_ACTION", "actor": "operator", "reason": "No action."},
    )
    assert close.status_code == 200
    assert close.json()["stage"] == "CLOSED_NO_ACTION"
    history = client.get(
        f"/api/v1/seo-investigations/{row.id}/history", params=query, headers=headers()
    ).json()["items"]
    assert [event["event_type"] for event in history] == ["CREATED", "CLOSE_NO_ACTION"]
