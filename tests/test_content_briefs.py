from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_query_page_intent import response
from test_seo_investigations import QUERY, URL, headers, investigation_scope, params

from gis.api.app import app
from gis.api.routes import database, router
from gis.content_briefs.service import ContentBriefError, ContentBriefService
from gis.evidence_gap_adjudication.service import EvidenceGapAdjudicationService
from gis.intelligence.provider import ReplayLLMProvider
from gis.models import (
    ContentBrief,
    ContentProposalReview,
    EvidenceCompatibility,
    EvidencePackage,
    EvidencePackageItem,
    Intervention,
    QueryPageIntentReview,
    RightsUsability,
    SourceIndependenceState,
)
from gis.query_page_intent.service import (
    GovernedReference,
    QueryPageIntentContext,
    QueryPageIntentService,
)

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


def ready_investigation(session: Session):  # type: ignore[no-untyped-def]
    tenant, site, market, query, page, gap, row, investigations = investigation_scope(session)
    package = session.get_one(EvidencePackage, gap.evidence_package_id)
    reference_id = uuid.uuid4()
    session.add(EvidencePackageItem(evidence_package_id=package.id,
        evidence_key="brief:governed-serp", evidence_type="EXACT_QUERY_SERP_SNAPSHOT",
        evidence_reference_id=reference_id, evidence_role="PRIMARY", root_source_key="fixture",
        independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE, supports_claim=True,
        metadata_json={"query": QUERY, "page_url": URL, "depth": 10}))
    session.flush()
    adjudication = EvidenceGapAdjudicationService(session).adjudicate(
        gap.id, tenant_id=tenant.id, site_id=site.id,
        evidence_package_ids=[package.id], evidence_reference_ids=[reference_id])
    context = QueryPageIntentContext(tenant_id=tenant.id, site_id=site.id,
        query_entity_id=query.id, page_entity_id=page.id, market_definition_id=market.id,
        exact_query=QUERY, candidate_url=URL,
        references=[GovernedReference(reference_id=reference_id,
            reference_type="SERP_RESULT", evidence_package_ids=[package.id], exact_query=QUERY,
            page_url=URL, market_definition_id=market.id, root_source="fixture")],
        page_content_claims=["A bounded owned-page observation exists."],
        serp_claims=["The candidate was observed within collected depth."],
        page_content_fingerprint="owned-v1", serp_fingerprint="serp-v1",
        quality={"freshness": "SUPPORTED"},
        limitations=["SERP non-observation outside collected depth is unknown."])
    payload = response(context)
    payload["candidate_url"] = URL
    assessment = QueryPageIntentService(session, ReplayLLMProvider(
        {"query_page_intent_resolution": payload})).resolve(context)
    session.add(QueryPageIntentReview(assessment_id=assessment.id, decision="CONFIRM",
        reviewer="operator", comment="Reviewed.", reviewed_at=assessment.evaluated_at))
    session.flush()
    investigations.apply(row, "MARK_READY_FOR_RECOMMENDATION", "operator", "All gates passed.")
    session.flush()
    return tenant, site, package, adjudication, assessment, row, reference_id, investigations


def test_incomplete_investigation_returns_all_failed_gates(session: Session) -> None:
    tenant, site, _, _, _, _, row, _ = investigation_scope(session)
    service = ContentBriefService(session)
    result = service.eligibility(row.id, tenant.id, site.id)
    assert result["eligible"] is False
    assert {item["gate"] for item in result["failed_gates"]} >= {
        "INVESTIGATION_STATE", "ADJUDICATION", "QUERY_PAGE_INTENT"}
    with pytest.raises(ContentBriefError, match="eligibility failed"):
        service.generate(row.id, tenant.id, site.id, actor="operator")
    assert session.scalar(select(func.count()).select_from(ContentBrief)) == 0


def test_ready_investigation_generates_bounded_idempotent_brief_and_proposals(
    session: Session,
) -> None:
    tenant, site, _, _, assessment, row, reference_id, investigations = ready_investigation(session)
    service = ContentBriefService(session)
    brief = service.generate(row.id, tenant.id, site.id, actor="operator")
    replay = service.generate(row.id, tenant.id, site.id, actor="operator")
    proposals = service.proposals(brief.id, tenant.id, site.id)
    assert replay.id == brief.id
    assert brief.llm_run_id is None and brief.prompt_version is None
    assert brief.assessment_id == assessment.id
    assert len(proposals) == 3
    assert all(str(reference_id) in item.supporting_reference_ids_json for item in proposals)
    assert all("Hypothesis" in item.expected_qualitative_effect for item in proposals)
    assert investigations.action(row)["action_type"] == "REVIEW_CONTENT_BRIEF"
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_review_is_append_only_and_approval_never_implements(session: Session) -> None:
    tenant, site, _, _, _, row, _, investigations = ready_investigation(session)
    service = ContentBriefService(session)
    brief = service.generate(row.id, tenant.id, site.id, actor="operator")
    proposal = service.proposals(brief.id, tenant.id, site.id)[0]
    first = service.review(proposal.id, tenant.id, site.id, reviewer="editor",
                           decision="REQUEST_CHANGES", comment="Clarify caveats.")
    second = service.review(proposal.id, tenant.id, site.id, reviewer="editor",
                            decision="APPROVE", comment="Bounded draft approved.")
    assert first.id != second.id
    assert proposal.status == "APPROVED"
    assert session.scalar(select(func.count()).select_from(ContentProposalReview)) == 2
    assert investigations.action(row)["action_type"] == "MARK_READY_FOR_MEASUREMENT_PLANNING"
    service.transition(proposal.id, tenant.id, site.id,
                       "MARK_READY_FOR_MEASUREMENT_PLANNING")
    assert proposal.status == "READY_FOR_MEASUREMENT_PLANNING"
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_stale_evidence_cross_scope_and_claim_boundaries_fail_closed(session: Session) -> None:
    tenant, site, package, _, _, row, _, _ = ready_investigation(session)
    service = ContentBriefService(session)
    brief = service.generate(row.id, tenant.id, site.id, actor="operator")
    proposal = service.proposals(brief.id, tenant.id, site.id)[0]
    package.identity_hash = uuid.uuid4().hex
    with pytest.raises(ContentBriefError, match="stale"):
        service.review(proposal.id, tenant.id, site.id, reviewer="editor",
                       decision="APPROVE", comment=None)
    assert proposal.status == "NEEDS_MORE_EVIDENCE"
    with pytest.raises(ContentBriefError, match="tenant/site"):
        service.scoped_brief(brief.id, uuid.uuid4(), site.id)
    with pytest.raises(ContentBriefError, match="Unsupported claim"):
        service._validate_claims({"text": "This change will improve rankings."})
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_brief_read_models_are_side_effect_free(session: Session) -> None:
    tenant, site, _, _, _, row, _, _ = ready_investigation(session)
    service = ContentBriefService(session)
    brief = service.generate(row.id, tenant.id, site.id, actor="operator")
    session.flush()
    review_count = session.scalar(select(func.count()).select_from(ContentProposalReview))
    intervention_count = session.scalar(select(func.count()).select_from(Intervention))
    assert service.brief_model(brief)["technical"]["llm_run_id"] is None
    assert service.briefs(row.id, tenant.id, site.id)[0].id == brief.id
    assert session.scalar(select(func.count()).select_from(ContentProposalReview)) == review_count
    assert session.scalar(select(func.count()).select_from(Intervention)) == intervention_count


def test_changed_governed_evidence_creates_linked_version(session: Session) -> None:
    tenant, site, package, _, _, row, _, _ = ready_investigation(session)
    service = ContentBriefService(session)
    first = service.generate(row.id, tenant.id, site.id, actor="operator")
    package.identity_hash = uuid.uuid4().hex
    second = service.generate(row.id, tenant.id, site.id, actor="operator")
    assert second.id != first.id
    assert second.previous_brief_id == first.id
    assert all(item.status == "SUPERSEDED" for item in service.proposals(
        first.id, tenant.id, site.id))


def test_content_brief_api_contract_is_registered() -> None:
    paths = {route.path for route in router.routes}
    assert {"/api/v1/seo-investigations/{resource_id}/brief-eligibility",
            "/api/v1/seo-investigations/{resource_id}/briefs/generate",
            "/api/v1/seo-investigations/{resource_id}/briefs",
            "/api/v1/seo-investigations/{resource_id}/briefs/{brief_id}",
            "/api/v1/content-briefs/{brief_id}/proposals",
            "/api/v1/page-change-proposals/{proposal_id}/reviews"} <= paths


def test_content_brief_api_generation_and_reads_are_explicit(
    client: TestClient, session: Session,
) -> None:
    tenant, site, _, _, _, row, _, _ = ready_investigation(session)
    session.commit()
    scope = params(tenant.id, site.id)
    eligibility = client.get(
        f"/api/v1/seo-investigations/{row.id}/brief-eligibility",
        params=scope, headers=headers(),
    )
    assert eligibility.status_code == 200 and eligibility.json()["eligible"] is True
    assert client.get(
        f"/api/v1/seo-investigations/{row.id}/briefs",
        params=scope, headers=headers(),
    ).json()["total"] == 0
    generated = client.post(
        f"/api/v1/seo-investigations/{row.id}/briefs/generate",
        params=scope, headers=headers("REVIEW"), json={"actor": "operator"},
    )
    assert generated.status_code == 201
    assert generated.json()["status"] == "READY_FOR_REVIEW"
    assert generated.json()["technical"]["llm_run_id"] is None
    assert client.get(
        f"/api/v1/seo-investigations/{row.id}/briefs",
        params=scope, headers=headers(),
    ).json()["total"] == 1
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0
