from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_opportunities import NOW, package

from gis.models import (
    DemandEvidenceStrength,
    Intervention,
    InterventionStatus,
    Recommendation,
    RecommendationCandidate,
    RecommendationReviewDecision,
    RecommendationRun,
    Site,
    Tenant,
)
from gis.opportunities.service import OpportunityService
from gis.recommendations.provider import FixtureRecommendationProvider, UnconfiguredExternalProvider
from gis.recommendations.service import RecommendationService
from gis.seed import seed


def supported_opportunity(session: Session):
    tenant, site, _ = package(session, DemandEvidenceStrength.SUPPORTED)
    opportunity = OpportunityService(session).detect(tenant.id, site.id, now=NOW)[0]
    return tenant, site, opportunity


def test_sparse_and_dry_run_make_zero_ai_calls(session: Session) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    provider = FixtureRecommendationProvider()
    assert OpportunityService(session).detect(tenant.id, site.id, now=NOW) == []
    _, _, opportunity = supported_opportunity(session)
    result = RecommendationService(session, provider).generate(opportunity.id, dry_run=True)
    assert result["status"] == "DRY_RUN" and provider.calls == 0
    assert session.scalar(select(func.count()).select_from(RecommendationRun)) == 0


def test_fixture_generation_is_structured_and_idempotent(session: Session) -> None:
    _, _, opportunity = supported_opportunity(session)
    provider = FixtureRecommendationProvider()
    service = RecommendationService(session, provider)
    first = service.generate(opportunity.id)
    second = service.generate(opportunity.id)
    assert first["status"] == "READY_FOR_REVIEW"
    assert first["candidate_count"] >= 1 and provider.calls == 1
    assert second["status"] == "REUSED" and second["recommendation_id"] == first["recommendation_id"]


@pytest.mark.parametrize(
    ("candidate_change", "expected_error"),
    [
        ({"intervention_type": "INVENTED_ACTION"}, "UNKNOWN_OR_INAPPLICABLE_INTERVENTION"),
        ({"target_metric": "INVENTED_METRIC"}, "UNKNOWN_METRIC"),
        ({"expected_magnitude": 42}, "UNSUPPORTED_EXPECTED_MAGNITUDE"),
    ],
)
def test_invalid_output_repair_is_bounded_and_persisted(
    session: Session, candidate_change: dict[str, object], expected_error: str
) -> None:
    _, _, opportunity = supported_opportunity(session)
    valid_provider = FixtureRecommendationProvider()
    context_service = RecommendationService(session, valid_provider)
    packages = context_service._packages(opportunity)
    valid = valid_provider.generate_structured_recommendation(context_service.context(opportunity, packages))
    valid["candidates"][0].update(candidate_change)
    provider = FixtureRecommendationProvider(valid)
    result = RecommendationService(session, provider).generate(opportunity.id)
    run = session.get(RecommendationRun, result["run_id"])
    assert result["status"] == "INVALID_OUTPUT" and expected_error in result["errors"]
    assert provider.calls == 2 and run and run.repair_attempts == 1


def test_external_provider_rights_gate_prevents_call(session: Session) -> None:
    _, _, opportunity = supported_opportunity(session)
    provider = UnconfiguredExternalProvider()
    result = RecommendationService(session, provider).generate(opportunity.id)
    assert result["status"] == "NO_VALID_RECOMMENDATION"
    assert "AI_INFERENCE_RIGHTS_NOT_ESTABLISHED" in result["blockers"]
    assert session.scalar(select(func.count()).select_from(RecommendationRun)) == 0


def test_acceptance_creates_draft_intervention_never_approval(session: Session) -> None:
    _, _, opportunity = supported_opportunity(session)
    service = RecommendationService(session, FixtureRecommendationProvider())
    result = service.generate(opportunity.id)
    candidate = session.scalar(select(RecommendationCandidate).where(RecommendationCandidate.recommendation_id == result["recommendation_id"]))
    assert candidate
    recommendation = service.review(result["recommendation_id"], RecommendationReviewDecision.ACCEPT, "human-reviewer", [candidate.id])
    intervention = session.get(Intervention, candidate.accepted_intervention_id)
    assert recommendation.status.value == "ACCEPTED"
    assert intervention and intervention.status is InterventionStatus.DRAFT


def test_candidate_and_tenant_isolation(session: Session) -> None:
    tenant, site, opportunity = supported_opportunity(session)
    service = RecommendationService(session, FixtureRecommendationProvider())
    result = service.generate(opportunity.id)
    assert len(service.list(tenant.id, site.id)) == 1
    assert service.list(uuid.uuid4(), site.id) == []
    with pytest.raises(ValueError, match="candidate does not belong"):
        service.review(result["recommendation_id"], RecommendationReviewDecision.ACCEPT, "reviewer", [uuid.uuid4()])
    assert session.scalar(select(func.count()).select_from(Recommendation)) == 1
