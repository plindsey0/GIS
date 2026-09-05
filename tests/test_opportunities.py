from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.evidence_quality.service import EvidenceQualityService
from gis.models import (
    AnalyticalEntityType,
    CorroborationState,
    DemandEvidenceStrength,
    EvidenceContract,
    EvidencePackage,
    EvidenceQualityRun,
    Opportunity,
    OpportunityEvaluation,
    OpportunityFamily,
    OpportunityStatus,
    RightsUsability,
    Site,
    SourceIndependenceState,
    Tenant,
)
from gis.opportunities.cli import run
from gis.opportunities.service import DETECTORS, VERSION, OpportunityService
from gis.opportunities.sufficiency import (
    candidate,
    collection_plan,
    detector_inventory,
    diagnose,
    portfolio,
)
from gis.seed import seed

NOW = datetime(2026, 8, 31, 12, tzinfo=timezone.utc)


def package(
    session: Session,
    sufficiency: DemandEvidenceStrength,
    *,
    rights: RightsUsability = RightsUsability.USABLE,
    conflicts: int = 0,
    visibility: str = "LOW",
    coverage: str | None = None,
) -> tuple[Tenant, Site, EvidencePackage]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    service = EvidenceQualityService(session)
    entity = service.entity(
        tenant.id,
        site.id,
        AnalyticalEntityType.QUERY,
        "va loan trend",
        metadata={"owned_visibility": visibility, "coverage_state": coverage},
    )
    contract = EvidenceContract(
        contract_key=f"TEST_{uuid.uuid4().hex}",
        contract_version="1",
        description="test",
        requirements_json={},
        active=True,
    )
    session.add(contract)
    session.flush()
    quality_run = EvidenceQualityRun(
        tenant_id=tenant.id,
        site_id=site.id,
        method_version="1",
        assessed_at=NOW,
        fingerprint=uuid.uuid4().hex,
        input_count=1,
        package_count=1,
        metadata_json={},
    )
    session.add(quality_run)
    session.flush()
    row = EvidencePackage(
        quality_run_id=quality_run.id,
        tenant_id=tenant.id,
        site_id=site.id,
        analytical_entity_id=entity.id,
        evidence_contract_id=contract.id,
        condition_key="demand",
        classification="EMERGING",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        sufficiency=sufficiency,
        identity_resolution="EXACT",
        source_independence=SourceIndependenceState.INDEPENDENT,
        corroboration=CorroborationState.CORROBORATED,
        rights_usability=rights,
        conflict_count=conflicts,
        independent_source_count=2,
        limitations_json=[],
        identity_hash=uuid.uuid4().hex,
        method_version="1",
    )
    session.add(row)
    session.flush()
    return tenant, site, row


def test_registry_version_and_sparse_behavior(session: Session) -> None:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    assert VERSION == "OPPORTUNITY_DETECTOR_V2"
    assert set(DETECTORS) == {
        "EMERGING_DEMAND_VISIBILITY_GAP",
        "DEMAND_ACCELERATION_GAP",
        "HIGH_VALUE_EVIDENCE_GAP",
        "COVERAGE_GAP",
        "DEMAND_GAP",
        "COMPETITIVE_GAP",
    }
    assert OpportunityService(session).detect(tenant.id, site.id, now=NOW) == []


def test_supported_package_activates_and_is_idempotent(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED)
    service = OpportunityService(session)
    first = service.detect(tenant.id, site.id, now=NOW)
    second = service.detect(tenant.id, site.id, now=NOW)
    active = [row for row in first if row.family is OpportunityFamily.DEMAND]
    assert len(active) == 1 and active[0].status is OpportunityStatus.ACTIVE
    assert active[0].condition_first_observed_at is None
    assert session.scalar(select(func.count()).select_from(Opportunity)) == 1
    assert session.scalar(select(func.count()).select_from(OpportunityEvaluation)) == 1
    assert len(second) == 1 and evidence.id


def test_limited_rights_conflict_and_visibility_gate(session: Session) -> None:
    tenant, site, _ = package(
        session, DemandEvidenceStrength.LIMITED, rights=RightsUsability.BLOCKED, conflicts=1
    )
    rows = OpportunityService(session).detect(tenant.id, site.id, now=NOW)
    assert rows and all(row.status is OpportunityStatus.WATCHING for row in rows)
    assert any("RIGHTS_BLOCKED" in row.limitations_json for row in rows)
    other_tenant = uuid.uuid4()
    assert OpportunityService(session).list(other_tenant, site.id) == []


def test_dismiss_restore_preserves_computed_state(session: Session) -> None:
    tenant, site, _ = package(session, DemandEvidenceStrength.SUPPORTED)
    service = OpportunityService(session)
    row = service.detect(tenant.id, site.id, now=NOW)[0]
    service.dismiss(row.id, "operator scope", "tester")
    assert (
        row.status is OpportunityStatus.DISMISSED
        and row.computed_status is OpportunityStatus.ACTIVE
    )
    service.restore(row.id, "tester")
    assert row.status is OpportunityStatus.ACTIVE


def test_cli_registry_is_json_ready() -> None:
    payload = run(["types"])
    assert payload["detector_version"] == VERSION
    assert all(
        "key" in detector and "materiality_components" in detector
        for detector in payload["detectors"]
    )


def test_sufficiency_hard_gates_and_first_observed_history(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.SUPPORTED)
    evidence.classification = "FIRST_OBSERVED"
    report = diagnose(session, tenant.id, site.id)
    result = report["items"][0]
    assert not result["qualifies"]
    emerging = next(
        item
        for item in result["detectors"]
        if item["detector_key"] == "EMERGING_DEMAND_VISIBILITY_GAP"
    )
    assert emerging["readiness"] == "WAITING_FOR_HISTORY"
    classification = next(
        item for item in emerging["conditions"] if item["key"] == "classification"
    )
    assert classification["remediation"] == "WAIT"
    assert report["diagnostics_materialization"] == "DERIVED_READ_MODEL"
    assert session.scalar(select(func.count()).select_from(Opportunity)) == 0


def test_sufficiency_candidate_plan_portfolio_are_read_only(session: Session) -> None:
    tenant, site, evidence = package(session, DemandEvidenceStrength.LIMITED)
    inventory = detector_inventory()
    assert {item["key"] for item in inventory["items"]} == set(DETECTORS)
    detail = candidate(session, tenant.id, site.id, evidence.id)
    assert detail["recommendation_context"]["llm_invoked"] is False
    assert detail["recommendation_context"]["state"] == "NOT_READY"
    plan = collection_plan(session, tenant.id, site.id)
    assert all(not item["provider_call"] for item in plan["actions"])
    assert plan["budget_scenarios"][0]["cost"] == 0
    target_portfolio = portfolio(session, tenant.id, site.id)
    assert "semantics" in target_portfolio
    assert session.scalar(select(func.count()).select_from(Opportunity)) == 0


def test_cross_sectional_coverage_claim_does_not_require_velocity(session: Session) -> None:
    tenant, site, evidence = package(
        session, DemandEvidenceStrength.SUPPORTED, coverage="NO_COVERAGE"
    )
    evidence.classification = "FIRST_OBSERVED"
    report = diagnose(session, tenant.id, site.id)
    coverage = next(
        row for row in report["items"][0]["detectors"] if row["detector_key"] == "COVERAGE_GAP"
    )
    emerging = next(
        row
        for row in report["items"][0]["detectors"]
        if row["detector_key"] == "EMERGING_DEMAND_VISIBILITY_GAP"
    )
    assert coverage["qualifies"] is True
    assert emerging["qualifies"] is False
    assert emerging["readiness"] == "WAITING_FOR_HISTORY"
