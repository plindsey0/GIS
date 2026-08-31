from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.evidence_quality.service import EvidenceQualityService
from gis.interventions.cli import run
from gis.interventions.service import VERSION, InterventionService
from gis.models import (
    AnalyticalEntityType,
    DemandEvidenceStrength,
    ExpectedDirection,
    Intervention,
    InterventionStatus,
    Opportunity,
    OpportunityFamily,
    OpportunityPriority,
    OpportunityStatus,
    Site,
    Tenant,
)
from gis.opportunities.service import OpportunityService, digest
from gis.seed import seed

NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)


def opportunity(session: Session, entity_type: AnalyticalEntityType = AnalyticalEntityType.URL) -> Opportunity:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    entity = EvidenceQualityService(session).entity(tenant.id, site.id, entity_type, "https://vahomemath.test/loan" if entity_type is AnalyticalEntityType.URL else "va loan")
    policy = OpportunityService(session).ensure_policies()["EMERGING_DEMAND_VISIBILITY_GAP"]
    row = Opportunity(tenant_id=tenant.id, site_id=site.id, analytical_entity_id=entity.id, detector_policy_id=policy.id, family=OpportunityFamily.DEMAND, opportunity_type="EMERGING_DEMAND_VISIBILITY_GAP", status=OpportunityStatus.ACTIVE, computed_status=OpportunityStatus.ACTIVE, priority=OpportunityPriority.HIGH, evidence_sufficiency=DemandEvidenceStrength.SUPPORTED, title="Supported demand condition", condition_description="Supported condition, not a recommendation.", detected_at=NOW, period_start=NOW.date(), period_end=NOW.date(), identity_hash=digest({"test": entity.id}), materiality_json={}, priority_components_json={}, limitations_json=[])
    session.add(row)
    session.flush()
    return row


def create(session: Session, opp: Opportunity | None = None) -> tuple[InterventionService, Opportunity, Intervention]:
    opp = opp or opportunity(session)
    service = InterventionService(session)
    row = service.create(opp.id, "UPDATE_CONTENT_ASSET", {"target_url": "https://vahomemath.test/loan", "content_scope": "factual sections"}, "GSC_CLICKS", ExpectedDirection.INCREASE, NOW - timedelta(days=28), NOW - timedelta(days=1), NOW + timedelta(days=7), NOW + timedelta(days=35), "The update is hypothesized to increase clicks because the linked opportunity remains active.")
    return service, opp, row


def test_registry_valid_types_and_sparse_behavior(session: Session) -> None:
    opp = opportunity(session)
    service = InterventionService(session)
    valid = service.valid_types(opp)
    assert {item["key"] for item in valid} >= {"UPDATE_CONTENT_ASSET", "CHANGE_PAGE_METADATA"}
    assert service.list(opp.tenant_id, opp.site_id) == []
    payload = run(["types"])
    assert payload["version"] == VERSION and payload["human_approval_required"] is True


def test_typed_validation_windows_and_idempotency(session: Session) -> None:
    opp = opportunity(session)
    service = InterventionService(session)
    errors = service.validate(opp, "UPDATE_CONTENT_ASSET", {}, "CRUX_LCP", NOW, NOW, NOW, NOW)
    assert "METRIC_UNSUPPORTED" in errors and "BASELINE_WINDOW_INVALID" in errors
    first = create(session, opp)[2]
    session.flush()
    duplicate = service.create(opp.id, "UPDATE_CONTENT_ASSET", {"target_url": "https://vahomemath.test/loan", "content_scope": "factual sections"}, "GSC_CLICKS", ExpectedDirection.INCREASE, NOW - timedelta(days=28), NOW - timedelta(days=1), NOW + timedelta(days=7), NOW + timedelta(days=35), "same")
    assert duplicate.id == first.id


def test_human_approval_lifecycle_and_invalid_transition(session: Session) -> None:
    service, _, row = create(session)
    service.transition(row.id, InterventionStatus.PROPOSED, actor="planner")
    with pytest.raises(ValueError, match="approval requires actor"):
        service.transition(row.id, InterventionStatus.APPROVED, actor=None)
    service.transition(row.id, InterventionStatus.APPROVED, actor="owner", reason="approved")
    assert row.status is InterventionStatus.APPROVED
    with pytest.raises(ValueError, match="invalid transition"):
        service.transition(row.id, InterventionStatus.MEASURED, actor="owner")


def test_insufficient_baseline_unknown_not_zero(session: Session) -> None:
    service, _, row = create(session)
    baseline = service.baseline(row.id)
    assert baseline["status"] == "INSUFFICIENT_BASELINE"
    assert baseline["value"] is None and baseline["causal_attribution"] is False
    assert baseline["provider_calls"] == 0


def test_tenant_isolation_and_no_recommendation_or_execution(session: Session) -> None:
    service, opp, row = create(session)
    assert service.list(opp.tenant_id, opp.site_id) == [row]
    assert service.list(opp.tenant_id, row.id) == []
    assert row.status is InterventionStatus.DRAFT
    assert row.feasibility.value == "UNKNOWN"
