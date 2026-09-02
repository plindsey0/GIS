from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.goals.service import GoalService, stable_hash
from gis.models import (
    DataRightsPolicy,
    DecompositionState,
    DerivationResultStatus,
    ObjectiveApproval,
    ObjectiveLifecycle,
    ObjectiveMeasurement,
    ObjectiveMeasurementHealth,
    ObjectiveOrigin,
    ObjectiveRelationshipType,
    ObjectiveType,
    RightsDecision,
    Site,
    StrategicObjective,
    TargetDirection,
    TargetFamily,
    Tenant,
)
from gis.seed import seed

NOW = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)


def context(session: Session) -> tuple[GoalService, Tenant, Site]:
    seed(session, hostname="vahomemath.test")
    tenant = session.scalar(select(Tenant).where(Tenant.slug == "vahomemath"))
    site = session.scalar(select(Site).where(Site.slug == "vahomemath"))
    assert tenant and site
    service = GoalService(session)
    service.ensure_registry()
    return service, tenant, site


def goal(
    session: Session,
    *,
    name: str = "Grow the business",
    goal_type: ObjectiveType = ObjectiveType.GROWTH,
    activate: bool = False,
) -> tuple[GoalService, StrategicObjective]:
    service, tenant, site = context(session)
    row = service.create_goal(
        tenant_id=tenant.id,
        site_id=site.id,
        name=name,
        objective_type=goal_type,
        actor="operator",
        activate=activate,
    )
    return service, row


def allowed_policy(session: Session, tenant: Tenant) -> DataRightsPolicy:
    policy = DataRightsPolicy(
        tenant_id=tenant.id,
        name="Objective fixture rights",
        commercial_use_allowed=RightsDecision.UNKNOWN,
        third_party_processing_allowed=RightsDecision.UNKNOWN,
        deterministic_analysis_allowed=RightsDecision.ALLOWED,
        ai_inference_allowed=RightsDecision.PROHIBITED,
        model_training_allowed=RightsDecision.PROHIBITED,
        raw_storage_allowed=RightsDecision.ALLOWED,
        derived_storage_allowed=RightsDecision.ALLOWED,
        raw_display_allowed=RightsDecision.UNKNOWN,
        derived_display_allowed=RightsDecision.ALLOWED,
        aggregation_allowed=RightsDecision.ALLOWED,
        cross_tenant_learning_allowed=RightsDecision.PROHIBITED,
        attribution_required=RightsDecision.UNKNOWN,
    )
    session.add(policy)
    session.flush()
    return policy


def revenue_fixture(
    session: Session,
    value: Decimal = Decimal("0.10"),
    *,
    freshness: str = "CURRENT",
    allow_rights: bool = True,
) -> tuple[GoalService, StrategicObjective]:
    service, tenant, site = context(session)
    metrics = service.ensure_registry()
    parent = service.create_goal(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Fixture revenue goal",
        objective_type=ObjectiveType.REVENUE,
        actor="operator",
        activate=True,
    )
    service.create_target(
        objective=parent,
        metric=metrics["MONTHLY_REVENUE"],
        family=TargetFamily.FINANCIAL,
        direction=TargetDirection.AT_LEAST,
        target_value=Decimal("10000"),
        actor="operator",
    )
    input_objective = service.create_goal(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Fixture monetization measurement",
        objective_type=ObjectiveType.EFFICIENCY,
        actor="fixture",
    )
    input_target = service.create_target(
        objective=input_objective,
        metric=metrics["REVENUE_PER_VISITOR"],
        family=TargetFamily.FINANCIAL,
        direction=TargetDirection.AT_LEAST,
        target_value=value,
        actor="fixture",
    )
    policy = allowed_policy(session, tenant) if allow_rights else None
    measurement = ObjectiveMeasurement(
        tenant_id=tenant.id,
        target_id=input_target.id,
        value=value,
        unit="currency_per_visitor",
        period_start=NOW - timedelta(days=30),
        period_end=NOW,
        measured_at=NOW,
        rights_policy_id=policy.id if policy else None,
        freshness_state=freshness,
        readiness_state="READY",
        method_key="FIXTURE_REVENUE_PER_VISITOR",
        method_version="1",
        identity_hash=stable_hash({"target": input_target.id, "value": value}),
    )
    session.add(measurement)
    session.flush()
    return service, parent


def test_user_authority_and_unmeasurable_goal(session: Session) -> None:
    service, row = goal(session)
    assert row.origin is ObjectiveOrigin.USER_DEFINED
    assert row.lifecycle is ObjectiveLifecycle.DRAFT
    assert row.measurement_health is ObjectiveMeasurementHealth.NOT_YET_MEASURABLE
    service.transition(row.id, row.tenant_id, row.site_id, ObjectiveLifecycle.ACTIVE, "operator")
    assert row.lifecycle is ObjectiveLifecycle.ACTIVE


def test_dag_allows_multiple_parents_and_rejects_cycles(session: Session) -> None:
    service, a = goal(session, name="A")
    _, b = goal(session, name="B")
    _, child = goal(session, name="Shared child")
    service.add_relationship(
        tenant_id=a.tenant_id,
        site_id=a.site_id,
        source_id=child.id,
        target_id=a.id,
        actor="operator",
    )
    service.add_relationship(
        tenant_id=a.tenant_id,
        site_id=a.site_id,
        source_id=child.id,
        target_id=b.id,
        actor="operator",
    )
    with pytest.raises(ValueError, match="cycle"):
        service.add_relationship(
            tenant_id=a.tenant_id,
            site_id=a.site_id,
            source_id=a.id,
            target_id=child.id,
            actor="operator",
        )


def test_tenant_isolation_on_relationships(session: Session) -> None:
    service, local = goal(session)
    other = Tenant(name="Other", slug="goals-other")
    session.add(other)
    session.flush()
    with pytest.raises(ValueError, match="scope"):
        service.add_relationship(
            tenant_id=other.id,
            site_id=local.site_id,
            source_id=local.id,
            target_id=local.id,
            actor="operator",
            relationship_type=ObjectiveRelationshipType.SUPPORTS,
        )


def test_deterministic_decomposition_and_idempotency(session: Session) -> None:
    service, parent = revenue_fixture(session)
    first = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    second = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    assert first.id == second.id
    assert first.output_value == Decimal("100000")
    assert first.rule_key == "REVENUE_TO_REQUIRED_TRAFFIC" and first.rule_version == "1"
    assert Decimal(first.input_values_json["revenue_per_qualified_visitor"]) == Decimal("0.10")
    child = session.get(StrategicObjective, first.generated_objective_id)
    assert child and child.origin is ObjectiveOrigin.DETERMINISTIC
    assert child.approval_state is ObjectiveApproval.PENDING
    assert child.lifecycle is ObjectiveLifecycle.PROPOSED


def test_missing_input_stops_without_inventing_target(session: Session) -> None:
    service, tenant, site = context(session)
    metrics = service.ensure_registry()
    parent = service.create_goal(
        tenant_id=tenant.id,
        site_id=site.id,
        name="Revenue",
        objective_type=ObjectiveType.REVENUE,
        actor="operator",
    )
    service.create_target(
        objective=parent,
        metric=metrics["MONTHLY_REVENUE"],
        family=TargetFamily.FINANCIAL,
        direction=TargetDirection.AT_LEAST,
        target_value=Decimal("10000"),
        actor="operator",
    )
    result = service.decompose(parent.id, tenant.id, site.id, "operator")
    assert result.result_status is DerivationResultStatus.BLOCKED
    assert parent.decomposition_state is DecompositionState.BLOCKED_MISSING_DATA
    assert result.generated_objective_id is None and "revenue-per-qualified-visitor" in (
        result.blocked_reason or ""
    )


@pytest.mark.parametrize(
    ("freshness", "rights", "state"),
    [
        ("CURRENT", False, DecompositionState.BLOCKED_RIGHTS),
        ("STALE", True, DecompositionState.BLOCKED_STALE_DATA),
    ],
)
def test_rights_and_freshness_block_decomposition(
    session: Session, freshness: str, rights: bool, state: DecompositionState
) -> None:
    service, parent = revenue_fixture(session, freshness=freshness, allow_rights=rights)
    result = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    assert result.result_status is DerivationResultStatus.BLOCKED
    assert parent.decomposition_state is state


def test_approval_and_user_override_preserve_suggestion(session: Session) -> None:
    service, parent = revenue_fixture(session)
    derivation = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    assert derivation.generated_objective_id and derivation.generated_target_id
    child = service.approve(
        derivation.generated_objective_id, parent.tenant_id, parent.site_id, "approver", True
    )
    assert (
        child.lifecycle is ObjectiveLifecycle.ACTIVE
        and child.approval_state is ObjectiveApproval.APPROVED
    )
    target = service.override_target(
        derivation.generated_target_id,
        parent.tenant_id,
        Decimal("60000"),
        "approver",
        "Approved lower operating target",
    )
    assert target.origin is ObjectiveOrigin.USER_OVERRIDE
    assert target.suggested_value == Decimal("100000") and target.target_value == Decimal("60000")


def test_recalculation_supersedes_derivation_not_parent(session: Session) -> None:
    service, parent = revenue_fixture(session)
    first = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    measurement = session.scalar(
        select(ObjectiveMeasurement).where(ObjectiveMeasurement.effective_end.is_(None))
    )
    assert measurement
    measurement.effective_end = NOW + timedelta(days=1)
    second_measurement = ObjectiveMeasurement(
        tenant_id=measurement.tenant_id,
        target_id=measurement.target_id,
        value=Decimal("0.20"),
        unit=measurement.unit,
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
        measured_at=NOW + timedelta(days=30),
        rights_policy_id=measurement.rights_policy_id,
        freshness_state="CURRENT",
        readiness_state="READY",
        method_key=measurement.method_key,
        method_version="1",
        identity_hash=stable_hash({"target": measurement.target_id, "value": "0.20"}),
    )
    session.add(second_measurement)
    session.flush()
    second = service.decompose(parent.id, parent.tenant_id, parent.site_id, "operator")
    assert first.result_status is DerivationResultStatus.SUPERSEDED
    assert second.output_value == Decimal("50000") and second.supersedes_derivation_id == first.id
    assert parent.name == "Fixture revenue goal" and parent.lifecycle is ObjectiveLifecycle.ACTIVE


def test_metric_appropriate_progress_and_unknowns(session: Session) -> None:
    service, objective = goal(session)
    metrics = service.ensure_registry()
    target = service.create_target(
        objective=objective,
        metric=metrics["GA4_SESSIONS"],
        family=TargetFamily.ABSOLUTE_METRIC,
        direction=TargetDirection.AT_LEAST,
        target_value=Decimal("25000"),
        actor="operator",
    )
    target.baseline_value, target.current_value = Decimal("10000"), Decimal("15000")
    assert GoalService.progress(target)["progress_percent"] == Decimal(
        "33.33333333333333333333333333"
    )
    rank = service.create_target(
        objective=objective,
        metric=metrics["QUERY_RANK"],
        family=TargetFamily.RANK,
        direction=TargetDirection.RANK_AT_OR_ABOVE,
        target_value=Decimal("5"),
        actor="operator",
    )
    rank.current_value = Decimal("18")
    result = GoalService.progress(rank)
    assert result["gap"] == Decimal("13") and result["progress_percent"] is None
    rank.current_value = None
    assert GoalService.progress(rank)["gap"] is None


def test_between_competitive_guardrail_and_measurement_snapshots(session: Session) -> None:
    service, objective = goal(session)
    metrics = service.ensure_registry()
    guardrail = service.create_target(
        objective=objective,
        metric=metrics["GSC_CTR"],
        family=TargetFamily.GUARDRAIL,
        direction=TargetDirection.BETWEEN,
        target_value=Decimal("0.03"),
        actor="operator",
    )
    guardrail.target_upper_value = Decimal("0.08")
    guardrail.current_value = Decimal("0.02")
    assert GoalService.progress(guardrail)["gap"] == Decimal("0.01")
    guardrail.current_value = Decimal("0.05")
    assert GoalService.progress(guardrail)["achieved"] is True
    competitive = service.create_target(
        objective=objective,
        metric=metrics["QUERY_RANK"],
        family=TargetFamily.COMPETITIVE,
        direction=TargetDirection.OUTRANK_ENTITY,
        target_value=None,
        condition={"competitor_rank": 4, "competitor": "fixture.example"},
        actor="operator",
    )
    competitive.current_value = Decimal("8")
    assert GoalService.progress(competitive)["gap"] == Decimal("5")
    assert GoalService.progress(competitive)["progress_percent"] is None
    first = service.record_measurement(
        target=guardrail,
        value=Decimal("0.04"),
        period_start=NOW - timedelta(days=7),
        period_end=NOW,
        measured_at=NOW,
        freshness_state="CURRENT",
        readiness_state="READY",
        method_key="FIXTURE_CTR",
        method_version="1",
    )
    duplicate = service.record_measurement(
        target=guardrail,
        value=Decimal("0.04"),
        period_start=NOW - timedelta(days=7),
        period_end=NOW,
        measured_at=NOW,
        freshness_state="CURRENT",
        readiness_state="READY",
        method_key="FIXTURE_CTR",
        method_version="1",
    )
    assert duplicate.id == first.id
    second = service.record_measurement(
        target=guardrail,
        value=None,
        period_start=NOW,
        period_end=NOW + timedelta(days=7),
        measured_at=NOW + timedelta(days=7),
        freshness_state="STALE",
        readiness_state="BLOCKED",
        method_key="FIXTURE_CTR",
        method_version="1",
    )
    assert first.effective_end == second.measured_at
    assert guardrail.current_value is None
    assert guardrail.measurement_health is ObjectiveMeasurementHealth.STALE_DATA
