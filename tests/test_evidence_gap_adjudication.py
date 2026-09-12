from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_investigation_handoff import URL, investigation
from test_query_page_intent import service as intent_service
from test_query_page_intent import setup_context

from gis.api.routes import router
from gis.api.semantics import evidence_gap_detail
from gis.evidence_gap_adjudication.service import (
    EvidenceGapAdjudicationError,
    EvidenceGapAdjudicationService,
)
from gis.investigations.service import InvestigationHandoffService
from gis.models import (
    CollectionPriorityTier,
    CollectionRequirementCapability,
    EvidenceCompatibility,
    EvidenceGap,
    EvidenceGapAdjudication,
    EvidenceGapAdjudicationReview,
    EvidencePackageItem,
    EvidenceReassessmentStatus,
    Intervention,
    RightsUsability,
    SourceIndependenceState,
)


def _scope(session: Session, monkeypatch: pytest.MonkeyPatch):
    tenant, site, evidence, proposal, provider = investigation(session, monkeypatch)
    requirement = next(
        row
        for row in InvestigationHandoffService(session).derive_requirements(proposal.id)
        if row.capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT
    )
    gap = EvidenceGap(
        id=requirement.gap_reference_id,
        evidence_package_id=evidence.id,
        collection_target_id=requirement.collection_target_id,
        gap_type=requirement.gap_type,
        description="Missing governed target-page content observation.",
        desired_evidence_capability="OWNED_PAGE_CONTENT",
        urgency=requirement.priority,
        identity_hash=uuid.uuid4().hex,
        provenance_metadata={"source": "provider_free_acceptance_fixture"},
    )
    session.add(gap)
    session.flush()
    requirement.evidence_gap_id = gap.id
    session.flush()
    return tenant, site, evidence, requirement, provider


def _add_owned_page_item(session: Session, package_id: uuid.UUID) -> EvidencePackageItem:
    item = EvidencePackageItem(
        evidence_package_id=package_id,
        evidence_key=f"content:{URL}",
        evidence_type="CONTENT_OBSERVATION",
        evidence_reference_id=uuid.uuid4(),
        evidence_role="TARGET_PAGE",
        root_source_key="direct_http",
        independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE,
        supports_claim=True,
        metadata_json={"url": URL},
    )
    session.add(item)
    session.flush()
    return item


def test_adjudication_api_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert {
        "/api/v1/evidence/gaps/{resource_id}/adjudications",
        "/api/v1/evidence/gaps/{resource_id}/current-adjudication",
        "/api/v1/evidence/gap-adjudications/{resource_id}/reviews",
        "/api/v1/evidence/gap-adjudications",
    } <= paths


def test_no_evidence_is_insufficient_and_collection_does_not_imply_satisfaction(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, _, requirement, provider = _scope(session, monkeypatch)
    calls_before = len(provider.calls)

    result = EvidenceGapAdjudicationService(session).adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[],
    )

    assert result.outcome == "STILL_INSUFFICIENT"
    assert requirement.reassessment_status is EvidenceReassessmentStatus.STILL_INSUFFICIENT
    assert requirement.intelligence_reassessment_eligible_at is None
    assert session.get_one(EvidenceGap, requirement.evidence_gap_id).resolved_at is None
    assert len(provider.calls) == calls_before
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_supported_exact_scope_satisfies_and_changed_state_versions_idempotently(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, package, requirement, _ = _scope(session, monkeypatch)
    service = EvidenceGapAdjudicationService(session)
    first = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[],
    )
    item = _add_owned_page_item(session, package.id)
    second = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
        evidence_reference_ids=[item.evidence_reference_id],
    )
    replay = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
        evidence_reference_ids=[item.evidence_reference_id],
    )

    assert second.outcome == "SATISFIED", second.reasons_json
    assert second.previous_adjudication_id == first.id
    assert first.is_current is False
    assert replay.id == second.id
    assert session.get_one(EvidenceGap, requirement.evidence_gap_id).resolved_at is not None
    assert requirement.intelligence_reassessment_eligible_at is not None
    assert session.scalar(select(func.count()).select_from(EvidenceGapAdjudication)) == 2


def test_wrong_scope_fabricated_reference_rights_and_conflict_fail_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, package, requirement, _ = _scope(session, monkeypatch)
    service = EvidenceGapAdjudicationService(session)
    item = _add_owned_page_item(session, package.id)
    with pytest.raises(EvidenceGapAdjudicationError, match="not governed"):
        service.adjudicate(
            requirement.evidence_gap_id,
            tenant_id=tenant.id,
            site_id=site.id,
            evidence_package_ids=[package.id],
            evidence_reference_ids=[uuid.uuid4()],
        )
    package.period_start = date(2020, 1, 1)
    package.period_end = date(2020, 1, 1)
    stale = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
    )
    assert stale.outcome == "PARTIALLY_SATISFIED"
    assert stale.freshness_assessment == "STALE"
    assert session.get_one(EvidenceGap, requirement.evidence_gap_id).resolved_at is None
    package.site_id = uuid.uuid4()
    with pytest.raises(EvidenceGapAdjudicationError, match="tenant/site scope"):
        service.adjudicate(
            requirement.evidence_gap_id,
            tenant_id=tenant.id,
            site_id=site.id,
            evidence_package_ids=[package.id],
        )
    package.site_id = site.id
    item.rights_usability = RightsUsability.BLOCKED
    blocked = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
    )
    assert blocked.outcome == "BLOCKED"
    assert session.get_one(EvidenceGap, requirement.evidence_gap_id).resolved_at is None
    item.rights_usability = RightsUsability.USABLE
    package.conflict_count = 1
    conflicting = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
    )
    assert conflicting.outcome == "CONFLICTING_EVIDENCE"
    assert session.get_one(EvidenceGap, requirement.evidence_gap_id).resolved_at is None


def test_reviews_are_append_only_and_workbench_detail_is_read_only(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, package, requirement, provider = _scope(session, monkeypatch)
    item = _add_owned_page_item(session, package.id)
    service = EvidenceGapAdjudicationService(session)
    result = service.adjudicate(
        requirement.evidence_gap_id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
        evidence_reference_ids=[item.id, item.evidence_reference_id],
    )
    service.review(
        result.id,
        tenant_id=tenant.id,
        site_id=site.id,
        decision="NEEDS_MORE_EVIDENCE",
        reviewer="operator",
        comment="Verify rendering state.",
    )
    service.review(
        result.id,
        tenant_id=tenant.id,
        site_id=site.id,
        decision="CONFIRM",
        reviewer="reviewer",
    )
    calls_before = len(provider.calls)
    detail = evidence_gap_detail(session, requirement.evidence_gap_id, tenant.id, site.id)

    assert detail["current_adjudication"]["human_review"]["state"] == "CONFIRM"
    assert detail["current_adjudication"]["recommended_next_action"]
    assert detail["current_adjudication"]["technical"]["input_fingerprint"]
    assert session.scalar(select(func.count()).select_from(EvidenceGapAdjudicationReview)) == 2
    assert len(provider.calls) == calls_before
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_combined_query_page_intent_evidence_requires_human_review_for_downstream_use(
    session: Session,
) -> None:
    tenant, site, package, entity, _, context = setup_context(session)
    resolver, provider, _ = intent_service(session, context)
    assessment = resolver.resolve(context)
    gap = EvidenceGap(
        evidence_package_id=package.id,
        gap_type="QUERY_PAGE_INTENT_SATISFACTION",
        description="Determine whether the candidate page satisfies the exact query intent.",
        desired_evidence_capability="QUERY_PAGE_INTENT",
        urgency=CollectionPriorityTier.HIGH,
        identity_hash=uuid.uuid4().hex,
        provenance_metadata={},
    )
    session.add(gap)
    session.flush()
    adjudicator = EvidenceGapAdjudicationService(session)

    result = adjudicator.adjudicate(
        gap.id,
        tenant_id=tenant.id,
        site_id=site.id,
        evidence_package_ids=[package.id],
        evidence_reference_ids=[assessment.id],
    )

    assert result.outcome == "SATISFIED"
    assert result.human_review_required is True
    assert result.downstream_reassessment_eligible is False
    assert gap.resolved_at is not None
    adjudicator.review(
        result.id,
        tenant_id=tenant.id,
        site_id=site.id,
        decision="CONFIRM",
        reviewer="operator",
    )
    assert adjudicator.read_model(result)["reassessment"]["eligible"] is True
    assert len(provider.calls) == 1 and provider.external is False
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0
