from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_content_briefs import ready_investigation
from test_gsc_ingestion import DateTransport, collector, provider_row, setup_connection
from test_seo_investigations import headers, params

from gis.api.app import app
from gis.api.routes import database
from gis.content_briefs.service import ContentBriefService
from gis.models import (
    DataRightsPolicy,
    Intervention,
    RightsDecision,
    SEOImplementationRecord,
    SEOMeasurementPlan,
    SEOMeasurementReview,
    SEOOutcomeAssessment,
)
from gis.seo_investigations.service import SEOInvestigationService
from gis.seo_measurement.service import SEOMeasurementError, SEOMeasurementService


@pytest.fixture()
def measurement_client(
    session: Session, monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setenv("GIS_API_OPERATOR_KEY", "epic-29a-test-key")

    def override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[database] = override
    with TestClient(app) as value:
        yield value
    app.dependency_overrides.clear()


def approved_proposal(session: Session):  # type: ignore[no-untyped-def]
    tenant, site, _, _, _, investigation, _, _ = ready_investigation(session)
    briefs = ContentBriefService(session)
    brief = briefs.generate(investigation.id, tenant.id, site.id, actor="operator")
    proposal = briefs.proposals(brief.id, tenant.id, site.id)[0]
    briefs.review(proposal.id, tenant.id, site.id, reviewer="editor",
                  decision="APPROVE", comment="Approved for bounded measurement.")
    session.flush()
    return tenant, site, investigation, proposal


def plan(session: Session):  # type: ignore[no-untyped-def]
    tenant, site, investigation, proposal = approved_proposal(session)
    row = SEOMeasurementService(session).create_plan(
        proposal.id, tenant.id, site.id, actor="operator",
        baseline_start=date(2026, 7, 1), baseline_end=date(2026, 7, 31),
        observation_start=date(2026, 8, 2), observation_end=date(2026, 8, 31))
    return tenant, site, investigation, proposal, row


def test_approved_proposal_creates_idempotent_versioned_plan(session: Session) -> None:
    tenant, site, investigation, proposal = approved_proposal(session)
    service = SEOMeasurementService(session)
    first = service.create_plan(proposal.id, tenant.id, site.id, actor="operator",
        baseline_start=date(2026, 7, 1), baseline_end=date(2026, 7, 31),
        observation_start=date(2026, 8, 2), observation_end=date(2026, 8, 31))
    replay = service.create_plan(proposal.id, tenant.id, site.id, actor="operator",
        baseline_start=date(2026, 7, 1), baseline_end=date(2026, 7, 31),
        observation_start=date(2026, 8, 2), observation_end=date(2026, 8, 31))
    changed = service.create_plan(proposal.id, tenant.id, site.id, actor="operator",
        baseline_start=date(2026, 6, 1), baseline_end=date(2026, 7, 31),
        observation_start=date(2026, 8, 2), observation_end=date(2026, 8, 31))
    assert replay.id == first.id
    assert changed.id != first.id and changed.previous_plan_id == first.id
    assert first.exact_query == "va down payment calculator"
    assert first.candidate_url == "https://vahomemath.com/va-entitlement-calculator"
    action = SEOInvestigationService(session).action(investigation)
    assert action["action_type"] == "CONFIRM_IMPLEMENTATION"
    assert action["destination"].endswith("/measurement")


def test_unapproved_stale_and_cross_scope_proposals_fail_closed(session: Session) -> None:
    tenant, site, _, proposal = approved_proposal(session)
    service = SEOMeasurementService(session)
    proposal.status = "DRAFT"
    assert service.eligibility(proposal.id, tenant.id, site.id)["eligible"] is False
    proposal.status = "APPROVED"
    proposal.evidence_fingerprint = "stale"
    with pytest.raises(SEOMeasurementError, match="stale"):
        service.create_plan(proposal.id, tenant.id, site.id, actor="operator",
            baseline_start=date(2026, 7, 1), baseline_end=date(2026, 7, 31),
            observation_start=date(2026, 8, 2), observation_end=date(2026, 8, 31))
    assert service.eligibility(proposal.id, uuid.uuid4(), site.id)["eligible"] is False


def test_implementation_is_explicit_append_only_and_never_intervenes(session: Session) -> None:
    tenant, site, _, proposal, measurement = plan(session)
    service = SEOMeasurementService(session)
    with pytest.raises(SEOMeasurementError, match="timestamp"):
        service.record_implementation(measurement.id, tenant.id, site.id,
            actor="operator", state="IMPLEMENTED", claimed_at=None,
            deployment_reference=None, categories=[proposal.category], deviations=[],
            concurrent_changes=[])
    first = service.record_implementation(measurement.id, tenant.id, site.id,
        actor="operator", state="IMPLEMENTED",
        claimed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        deployment_reference="deploy-123", categories=[proposal.category], deviations=[],
        concurrent_changes=[])
    second = service.record_implementation(measurement.id, tenant.id, site.id,
        actor="operator", state="ROLLED_BACK",
        claimed_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        deployment_reference="deploy-123", categories=[proposal.category], deviations=[],
        concurrent_changes=[], rollback_reference="rollback-456")
    assert first.id != second.id
    assert session.scalar(select(func.count()).select_from(SEOImplementationRecord)) == 2
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0


def test_governed_gsc_outcome_is_deterministic_bounded_and_reviewed(session: Session) -> None:
    connection = setup_connection(session)
    tenant, site, _, proposal, measurement = plan(session)
    assert connection.site_id == site.id
    connection.configuration_json = {**connection.configuration_json,
        "country": measurement.scope_dimensions_json["country"],
        "device": measurement.scope_dimensions_json["device"]}
    session.flush()
    transport = DateTransport({
        "2026-07-15": [provider_row("2026-07-15", clicks=10,
            query=measurement.exact_query, page=measurement.candidate_url)],
        "2026-08-15": [provider_row("2026-08-15", clicks=20,
            query=measurement.exact_query, page=measurement.candidate_url)],
    })
    collector(session, connection, transport).sync(
        connection.id, date(2026, 7, 15), date(2026, 8, 15))
    service = SEOMeasurementService(session)
    assert service.compatible_gsc(measurement) == []
    for policy in session.scalars(select(DataRightsPolicy)):
        policy.deterministic_analysis_allowed = RightsDecision.ALLOWED
        policy.derived_storage_allowed = RightsDecision.ALLOWED
    session.flush()
    implementation = service.record_implementation(measurement.id, tenant.id, site.id,
        actor="operator", state="IMPLEMENTED",
        claimed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        deployment_reference="deploy-123", categories=[proposal.category], deviations=[],
        concurrent_changes=["Navigation update"])
    evidence = service.compatible_gsc(measurement)
    assert len(evidence) == 2
    assert service.baseline_readiness(measurement)["ready"] is True
    assessment = service.assess(measurement.id, tenant.id, site.id,
        as_of=datetime(2026, 9, 1, tzinfo=timezone.utc),
        evidence_reference_ids=[row.id for row in evidence])
    replay = service.assess(measurement.id, tenant.id, site.id,
        as_of=datetime(2026, 9, 1, tzinfo=timezone.utc),
        evidence_reference_ids=[row.id for row in evidence])
    assert replay.id == assessment.id
    assert assessment.causal_classification == "CAUSALITY_NOT_ESTABLISHED"
    assert any("Concurrent changes" in item for item in assessment.limitations_json)
    assert assessment.outcome_state == "MIXED_OR_CONFLICTING"
    review = service.review(measurement.id, tenant.id, site.id,
        artifact_type="IMPLEMENTATION", artifact_id=implementation.id,
        reviewer="reviewer", decision="CONFIRM", comment="Verified record.", follow_up=[])
    assert review.id is not None
    assert session.scalar(select(func.count()).select_from(SEOMeasurementReview)) == 1
    assert session.scalar(select(func.count()).select_from(SEOOutcomeAssessment)) == 1
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0
    connection.configuration_json = {**connection.configuration_json, "country": "GB"}
    session.flush()
    assert service.compatible_gsc(measurement) == []


def test_unknown_or_post_change_baseline_evidence_fails(session: Session) -> None:
    tenant, site, _, proposal, measurement = plan(session)
    service = SEOMeasurementService(session)
    service.record_implementation(measurement.id, tenant.id, site.id,
        actor="operator", state="IMPLEMENTED",
        claimed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        deployment_reference=None, categories=[proposal.category], deviations=[],
        concurrent_changes=[])
    with pytest.raises(SEOMeasurementError, match="Unknown"):
        service.assess(measurement.id, tenant.id, site.id,
            as_of=datetime(2026, 9, 1, tzinfo=timezone.utc),
            evidence_reference_ids=[uuid.uuid4()])
    assert session.scalar(select(func.count()).select_from(SEOOutcomeAssessment)) == 0


def test_measurement_api_contract_is_registered() -> None:
    from gis.api.routes import router

    paths = {route.path for route in router.routes}
    assert {"/api/v1/page-change-proposals/{proposal_id}/measurement-eligibility",
        "/api/v1/page-change-proposals/{proposal_id}/measurement-plans",
        "/api/v1/seo-investigations/{resource_id}/measurement-plans",
        "/api/v1/seo-measurement-plans/{plan_id}",
        "/api/v1/seo-measurement-plans/{plan_id}/implementations",
        "/api/v1/seo-measurement-plans/{plan_id}/assessments",
        "/api/v1/seo-measurement-plans/{plan_id}/reviews"} <= paths


def test_measurement_reads_are_side_effect_free(session: Session) -> None:
    tenant, site, investigation, _, measurement = plan(session)
    service = SEOMeasurementService(session)
    before = session.scalar(select(func.count()).select_from(SEOMeasurementPlan))
    assert service.plan_model(measurement)["exact_query"] == "va down payment calculator"
    assert service.plans(investigation.id, tenant.id, site.id)[0].id == measurement.id
    assert session.scalar(select(func.count()).select_from(SEOMeasurementPlan)) == before


def test_measurement_api_creation_is_explicit(
    measurement_client: TestClient, session: Session,
) -> None:
    tenant, site, investigation, proposal = approved_proposal(session)
    session.commit()
    scope = params(tenant.id, site.id)
    assert measurement_client.get(f"/api/v1/page-change-proposals/{proposal.id}/measurement-eligibility",
        params=scope, headers=headers()).json()["eligible"] is True
    assert measurement_client.get(f"/api/v1/seo-investigations/{investigation.id}/measurement-plans",
        params=scope, headers=headers()).json()["total"] == 0
    response = measurement_client.post(f"/api/v1/page-change-proposals/{proposal.id}/measurement-plans",
        params=scope, headers=headers("REVIEW"), json={"actor": "operator",
            "baseline_start": "2026-07-01", "baseline_end": "2026-07-31",
            "observation_start": "2026-08-02", "observation_end": "2026-08-31"})
    assert response.status_code == 201
    assert response.json()["status"] == "AWAITING_BASELINE"
    assert session.scalar(select(func.count()).select_from(Intervention)) == 0
