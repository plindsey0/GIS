from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_governed_intelligence import responses, setup

from gis.api.semantics import collection_inventory
from gis.api.workbench import WorkbenchQueries
from gis.intelligence.service import EvidencePacketService, IntelligenceValidationError
from gis.investigations.service import InvestigationHandoffService
from gis.market_intelligence.service import MarketIntelligenceService
from gis.models import (
    CollectionRequirement,
    CollectionRequirementCapability,
    CollectionRequirementStatus,
    EvidenceCompatibility,
    EvidencePackageItem,
    EvidenceReassessmentStatus,
    ExperimentProposalReview,
    Intervention,
    ProposalArtifactType,
    RightsUsability,
    ScheduledTarget,
    SourceIndependenceState,
    TrackedQuery,
)
from gis.orchestration.seed import seed_vahomemath_cadence

NOW = datetime(2026, 9, 8, 12, tzinfo=timezone.utc)
QUERY = "va down payment calculator"
URL = "https://www.vahomemath.com/va-entitlement-calculator/"


def investigation(session: Session, monkeypatch: pytest.MonkeyPatch):
    tenant, site, evidence, packet, provider, intelligence = setup(session)
    opportunity = intelligence.generate_opportunities(packet)[0]
    intelligence.review_opportunity(opportunity.id, "ACCEPTED", "operator")
    provider.responses.update(responses(evidence.id, opportunity_id=opportunity.id))
    recommendation = intelligence.generate_recommendations([opportunity.id])[0]
    tracked_query = TrackedQuery(
        tenant_id=tenant.id,
        site_id=site.id,
        query_text=QUERY,
        normalized_query=QUERY,
        country_code="US",
        language_code="en",
        device="desktop",
        requested_depth=100,
    )
    session.add(tracked_query)
    session.flush()
    market = MarketIntelligenceService(session).define(
        tenant_id=tenant.id,
        site_id=site.id,
        name=f"Investigation market {uuid.uuid4()}",
        slug=f"investigation-{uuid.uuid4()}",
        tracked_query_ids=[tracked_query.id],
    )
    opportunity.market_definition_id = market.id
    opportunity.market_definition_version = market.version
    recommendation.market_definition_id = market.id
    recommendation.market_definition_version = market.version
    seed_vahomemath_cadence(session)
    intelligence.select_recommendation(
        recommendation.id, "operator", "Do not change the page before evidence collection."
    )
    provider.responses.update(responses(evidence.id, opportunity.id, recommendation.id))
    proposal = intelligence.generate_experiment_proposal(recommendation.id)
    proposal.proposal_type = ProposalArtifactType.INVESTIGATION
    proposal.status = "APPROVED"
    proposal.target_url_or_resource = URL
    session.add(ExperimentProposalReview(
        experiment_proposal_id=proposal.id,
        decision="APPROVED",
        reviewer="operator",
        comment="Observation only; no live treatment and no automatic paid collection.",
        reviewed_at=NOW,
    ))
    packet.entity_context = {
        "canonical_key": QUERY,
        "country_code": "US",
        "language_code": "en",
        "device": "desktop",
    }
    packet.owned_surfaces = [{"url": URL, "relationship": "GOVERNED_CANDIDATE"}]
    packet.evidence_gaps = [
        {
            "gap_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "owned-page-gap")),
            "gap_type": "TARGET_PAGE_CONTENT_OBSERVATION",
            "description": "Missing governed target-page content observation.",
        },
        {
            "gap_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "exact-serp-gap")),
            "gap_type": "EXACT_QUERY_SERP_COMPETITOR_EVIDENCE",
            "description": "Missing governed exact-query SERP observation.",
        },
        {
            "gap_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "unsupported-gap")),
            "gap_type": "CALCULATOR_CORRECTNESS_AUDIT",
            "description": "A calculator correctness audit is not a collection capability.",
        },
    ]
    monkeypatch.setattr(
        EvidencePacketService,
        "build_for_entity",
        lambda _self, _tenant, _site, _entity, **_kwargs: packet,
    )
    return tenant, site, evidence, proposal, provider


def test_investigation_derives_governed_requirements_idempotently(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant, site, _, proposal, provider = investigation(session, monkeypatch)
    calls_before = len(provider.calls)
    service = InvestigationHandoffService(session)
    first = service.derive_requirements(proposal.id)
    second = service.derive_requirements(proposal.id)

    assert [row.id for row in first] == [row.id for row in second]
    assert session.scalar(select(func.count()).select_from(CollectionRequirement)) == 3
    owned = next(row for row in first if row.capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT)
    serp = next(row for row in first if row.capability is CollectionRequirementCapability.EXACT_QUERY_SERP)
    unsupported = next(row for row in first if row.capability is CollectionRequirementCapability.UNSUPPORTED)
    assert owned.target_value == URL
    assert serp.target_value == QUERY
    assert (serp.country_code, serp.language_code, serp.device) == ("US", "en", "desktop")
    assert unsupported.status is CollectionRequirementStatus.UNSUPPORTED
    assert "calculator correctness" in unsupported.unsupported_characteristics_json[0].lower()
    assert "no automatic paid collection" in " ".join(owned.human_constraints_json).lower()
    assert len(provider.calls) == calls_before
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0

    detail = WorkbenchQueries(session).experiment_proposal(proposal)
    assert len(detail["collection_requirements"]) == 3
    inventory = collection_inventory(
        session, tenant.id, site.id, page=1, limit=25,
        origin="INTELLIGENCE_REQUESTED", search=QUERY, capability="EXACT_QUERY_SERP",
    )
    assert inventory["total"] == 1
    assert inventory["items"][0]["proposal_title"] == proposal.title
    service.promote_to_candidate_plan(serp.id, "operator")
    assert serp.collection_target_id is not None
    assert serp.collection_plan_item_id is not None
    assert serp.status is CollectionRequirementStatus.CANDIDATE
    assert serp.provider_key == "dataforseo"
    assert serp.cost_class == "KNOWN_PAID"
    assert session.scalar(select(func.count()).select_from(ScheduledTarget)) == 0


def test_experiment_and_unapproved_investigation_cannot_derive(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, proposal, _ = investigation(session, monkeypatch)
    proposal.proposal_type = ProposalArtifactType.EXPERIMENT
    with pytest.raises(IntelligenceValidationError, match="investigation proposal"):
        InvestigationHandoffService(session).derive_requirements(proposal.id)
    proposal.proposal_type = ProposalArtifactType.INVESTIGATION
    proposal.status = "READY_FOR_REVIEW"
    with pytest.raises(IntelligenceValidationError, match="human approval"):
        InvestigationHandoffService(session).derive_requirements(proposal.id)


def test_reassessment_requires_sufficient_governed_evidence_and_never_executes(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, evidence, proposal, provider = investigation(session, monkeypatch)
    service = InvestigationHandoffService(session)
    requirement = next(
        row for row in service.derive_requirements(proposal.id)
        if row.capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT
    )
    calls_before = len(provider.calls)
    service.reassess(requirement.id, None)
    assert requirement.reassessment_status is EvidenceReassessmentStatus.STILL_INSUFFICIENT
    assert requirement.intelligence_reassessment_eligible_at is None

    session.add(EvidencePackageItem(
        evidence_package_id=evidence.id,
        evidence_key=f"content:{URL}",
        evidence_type="CONTENT_OBSERVATION",
        evidence_role="TARGET_PAGE",
        root_source_key="direct_http",
        independence=SourceIndependenceState.INDEPENDENT,
        method_compatibility=EvidenceCompatibility.COMPATIBLE,
        scope_compatibility=EvidenceCompatibility.COMPATIBLE,
        rights_usability=RightsUsability.USABLE,
        supports_claim=True,
        metadata_json={"url": URL},
    ))
    session.flush()
    service.reassess(requirement.id, evidence.id)
    assert requirement.status is CollectionRequirementStatus.SATISFIED
    assert requirement.reassessment_status is EvidenceReassessmentStatus.SATISFIED
    assert requirement.intelligence_reassessment_eligible_at is not None
    assert len(provider.calls) == calls_before
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_tenant_site_and_entity_scope_remain_enforced(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, evidence, proposal, _ = investigation(session, monkeypatch)
    requirement = InvestigationHandoffService(session).derive_requirements(proposal.id)[0]
    evidence.site_id = uuid.uuid4()
    with pytest.raises(IntelligenceValidationError, match="outside requirement scope"):
        InvestigationHandoffService(session).reassess(requirement.id, evidence.id)
