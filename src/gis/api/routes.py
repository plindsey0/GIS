from __future__ import annotations

import os
import uuid
from dataclasses import asdict
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from gis.api.auth import Role, require_role
from gis.api.errors import ApiError
from gis.api.schemas import (
    DecisionInput,
    GenerationInput,
    GoalCreateInput,
    GoalRelationshipInput,
    GoalTargetInput,
    GoalUpdateInput,
    Health,
    OpportunitySummary,
    Page,
    ProviderActionInput,
    ProviderCapabilityInput,
    ProviderPolicyInput,
    ProviderPreflightInput,
    ProviderTargetInput,
    ProviderTargetStatusInput,
    RecommendationReviewInput,
    ResourceDetail,
    SiteContext,
    TargetOverrideInput,
)
from gis.api.semantics import (
    collection_detail as semantic_collection_detail,
)
from gis.api.semantics import (
    collection_inventory,
    evidence_gap_detail,
    evidence_inventory,
    opportunity_diagnostics,
)
from gis.api.semantics import (
    evidence_detail as semantic_evidence_detail,
)
from gis.api.semantics import (
    market_detail as semantic_market_detail,
)
from gis.api.system import SystemQueries
from gis.api.workbench import WorkbenchQueries, row_data
from gis.db import session_factory
from gis.goals.service import GoalService
from gis.interventions.service import InterventionService
from gis.models import (
    DecompositionPlan,
    EvidencePackage,
    Experiment,
    Intervention,
    InterventionHypothesis,
    InterventionLifecycleEvent,
    InterventionOutcome,
    InterventionStatus,
    MarketDefinition,
    MeasurementContract,
    MetricDefinition,
    ObjectiveAuditEvent,
    ObjectiveDerivation,
    ObjectiveLifecycle,
    ObjectiveMeasurement,
    ObjectiveRelationship,
    ObjectiveRelationshipType,
    ObjectiveTarget,
    ObjectiveType,
    Opportunity,
    OpportunityEvaluation,
    OpportunityEvidence,
    Recommendation,
    RecommendationCandidate,
    RecommendationEvidence,
    RecommendationReview,
    RecommendationReviewDecision,
    Site,
    StrategicObjective,
    TargetDirection,
    TargetFamily,
)
from gis.opportunities.service import OpportunityService
from gis.orchestration.service import Orchestrator
from gis.provenance.review import (
    RightsReviewInput,
    review_context,
    review_policy,
    scoped_connection,
)
from gis.provider_control.binding import reconcile_schedules, schedules_for
from gis.provider_control.configuration import CollectionConfiguration, ConfigurationService
from gis.provider_control.manual import ManualRequest, manual_run
from gis.provider_control.recovery import recovery_preview
from gis.provider_control.runtime import readiness
from gis.provider_control.service import ProviderControlService
from gis.recommendations.provider import FixtureRecommendationProvider
from gis.recommendations.service import RecommendationService


def database() -> Session:  # type: ignore[misc]
    with session_factory()() as session:
        yield session


router = APIRouter(prefix="/api/v1")


@router.get("/connections/{connection_id}/rights", dependencies=[Depends(require_role(Role.READ))])
def connection_rights(
    connection_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, object]:
    try:
        return review_context(
            session, scoped_connection(session, connection_id, tenant_id, site_id)
        )
    except ValueError as error:
        raise ApiError(404, "CONNECTION_NOT_FOUND", str(error)) from error


@router.post(
    "/connections/{connection_id}/rights/reviews", dependencies=[Depends(require_role(Role.ADMIN))]
)
def review_connection_rights(
    connection_id: uuid.UUID,
    payload: RightsReviewInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, object]:
    try:
        connection = scoped_connection(session, connection_id, tenant_id, site_id, lock=True)
        policy = review_policy(session, connection, payload)
        session.commit()
        context = review_context(session, connection)
        return {
            "approval": {
                "policy_id": str(policy.id),
                "version": policy.policy_version,
                "effective_at": policy.effective_at.isoformat() if policy.effective_at else None,
                "reviewed_at": policy.reviewed_at.isoformat() if policy.reviewed_at else None,
                "supersedes_policy_id": (
                    str(policy.supersedes_policy_id) if policy.supersedes_policy_id else None
                ),
            },
            "current": context,
        }
    except ValueError as error:
        session.rollback()
        raise ApiError(409, "RIGHTS_REVIEW_REJECTED", str(error)) from error
    except SQLAlchemyError as error:
        session.rollback()
        raise ApiError(
            500,
            "RIGHTS_REVIEW_FAILED",
            "Rights review could not be persisted; no policy was activated.",
            retryable=True,
        ) from error


class AccountRefreshInput(BaseModel):
    actor: str = Field(min_length=1, max_length=255)
    confirmed: bool = False


@router.post(
    "/connections/{connection_id}/account-telemetry/refresh",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def refresh_connection_account(
    connection_id: uuid.UUID,
    payload: AccountRefreshInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    from gis.integrations.builtwith.telemetry import refresh, telemetry_status

    try:
        if not payload.confirmed:
            raise ValueError("Explicit account telemetry confirmation required")
        connection = scoped_connection(session, connection_id, tenant_id, site_id, lock=True)
        refresh(session, connection, payload.actor)
        session.commit()
        return telemetry_status(session, connection)
    except ValueError as error:
        session.rollback()
        raise ApiError(409, "ACCOUNT_REFRESH_BLOCKED", str(error)) from error


@router.get(
    "/providers/{provider_key}/configuration", dependencies=[Depends(require_role(Role.READ))]
)
def provider_configuration(
    provider_key: str,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        result = ConfigurationService(session).read(tenant_id, site_id, provider_key)
        result["schedules"] = schedules_for(
            session, tenant_id, site_id, ProviderControlService(session).provider(provider_key).id
        )
        return result
    except ValueError as exc:
        raise ApiError(404, "PROVIDER_CONFIGURATION_NOT_FOUND", str(exc)) from exc


@router.post(
    "/providers/{provider_key}/configuration/preview",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def preview_provider_configuration(
    provider_key: str,
    payload: CollectionConfiguration,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        return ConfigurationService(session).preview(tenant_id, site_id, provider_key, payload)
    except ValueError as exc:
        raise ApiError(409, "PROVIDER_CONFIGURATION_INVALID", str(exc)) from exc


@router.put(
    "/providers/{provider_key}/configuration", dependencies=[Depends(require_role(Role.ADMIN))]
)
def save_provider_configuration(
    provider_key: str,
    payload: CollectionConfiguration,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        result = ConfigurationService(session).save(tenant_id, site_id, provider_key, payload)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise ApiError(409, "PROVIDER_CONFIGURATION_INVALID", str(exc)) from exc


@router.post("/providers/{provider_key}/run", dependencies=[Depends(require_role(Role.ADMIN))])
def provider_manual_run(
    provider_key: str,
    payload: ManualRequest,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        if not payload.target_ids:
            raise ValueError(
                "Manual preview requires explicit targets. Reload the Workbench and use the manual scope selector before previewing."
            )
        from gis.models import DataSourceConnection

        control = ProviderControlService(session)
        policy = control.policy(tenant_id, site_id, control.provider(provider_key).id)
        health = (
            readiness(
                session,
                session.get(DataSourceConnection, policy.data_source_connection_id)
                if policy and policy.data_source_connection_id
                else None,
            )
            if provider_key in {"dataforseo", "builtwith"}
            else None
        )
        if payload.confirmed and health and not health["runnable"]:
            raise ValueError(health["reason"])
        result = manual_run(session, tenant_id, site_id, provider_key, payload)
        if health and not health["runnable"]:
            result["blockers"].append(health["reason"])
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise ApiError(409, "PROVIDER_RUN_BLOCKED", str(exc)) from exc


@router.get(
    "/providers/{provider_key}/manual-scope", dependencies=[Depends(require_role(Role.ADMIN))]
)
def provider_manual_scope(
    provider_key: str,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    """Discover authorized choices independently of a runnable execution preview."""
    result = manual_run(
        session, tenant_id, site_id, provider_key, ManualRequest(request_id=uuid.uuid4())
    )
    return {
        "scope_contract_version": result["scope_contract_version"],
        "choices": result["choices"],
    }


def disable_partial_configuration(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID, key: str, actor: str
) -> None:
    """Legacy granular edits are drafts, never an alternate activation path."""
    policy = ProviderControlService(session).transition(
        tenant_id,
        site_id,
        key,
        "DISABLE",
        actor,
        "Partial configuration edit; review configuration before activation",
    )
    reconcile_schedules(session, policy)


@router.post(
    "/providers/{provider_key}/recover/{run_id}", dependencies=[Depends(require_role(Role.ADMIN))]
)
def provider_recover(
    provider_key: str,
    run_id: uuid.UUID,
    payload: ManualRequest,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    from gis.models import (
        DataSourceConnection,
        OrchestrationRun,
        ProviderCapabilityPolicy,
        ProviderCollectionPolicy,
    )

    try:
        run = session.scalar(
            select(OrchestrationRun)
            .where(
                OrchestrationRun.id == run_id,
                OrchestrationRun.tenant_id == tenant_id,
                OrchestrationRun.site_id == site_id,
            )
            .with_for_update()
        )
        if not run:
            raise ValueError("Execution not found in this site")
        cp = session.get(
            ProviderCapabilityPolicy,
            uuid.UUID(str(run.configuration_json.get("provider_capability_policy_id"))),
        )
        policy = session.get(ProviderCollectionPolicy, cp.collection_policy_id) if cp else None
        control = ProviderControlService(session)
        if not policy or policy.provider_id != control.provider(provider_key).id:
            raise ValueError("Execution does not belong to this provider")
        check = recovery_preview(session, run)
        connection = (
            session.get(DataSourceConnection, run.data_source_connection_id)
            if run.data_source_connection_id
            else None
        )
        health = readiness(session, connection) if provider_key == "dataforseo" else None
        if health and not health["runnable"]:
            check["blockers"].append(health["reason"])
            check["can_retry"] = False
        if payload.confirmed:
            if payload.fingerprint != check["fingerprint"] or check["blockers"]:
                raise ValueError("Recovery requires a current unblocked preview")
            control._audit(
                policy,
                "OBLIGATION_RECOVERY_REQUESTED",
                "workbench-admin",
                "Explicit operator retry confirmation",
                {"run_id": str(run.id), "failure": run.error_detail},
                {"obligation_id": str(run.obligation_id), "request_id": str(payload.request_id)},
            )
            Orchestrator(session).retry(tenant_id, run.id)
        return {**check, "queued": payload.confirmed}
    except (ValueError, RuntimeError) as exc:
        session.rollback()
        raise ApiError(409, "RECOVERY_BLOCKED", str(exc)) from exc


@router.get("/providers", dependencies=[Depends(require_role(Role.READ))])
def providers(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return ProviderControlService(session).inventory(tenant_id, site_id)


@router.get("/providers/{provider_key}", dependencies=[Depends(require_role(Role.READ))])
def provider_detail(
    provider_key: str,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        return ProviderControlService(session).detail(tenant_id, site_id, provider_key)
    except ValueError as exc:
        raise ApiError(404, "PROVIDER_NOT_FOUND", str(exc)) from exc


@router.put("/providers/{provider_key}/policy", dependencies=[Depends(require_role(Role.ADMIN))])
def provider_policy(
    provider_key: str,
    payload: ProviderPolicyInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        service.configure(
            tenant_id,
            site_id,
            provider_key,
            payload.model_dump(exclude={"actor", "reason"}),
            payload.actor,
            payload.reason,
        )
    except (ValueError, KeyError) as exc:
        raise ApiError(409, "PROVIDER_POLICY_INVALID", str(exc)) from exc
    disable_partial_configuration(session, tenant_id, site_id, provider_key, payload.actor)
    session.commit()
    return service.detail(tenant_id, site_id, provider_key)


@router.post("/providers/{provider_key}/actions", dependencies=[Depends(require_role(Role.ADMIN))])
def provider_action(
    provider_key: str,
    payload: ProviderActionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        if payload.action in {"ENABLE", "RESUME"}:
            current = ConfigurationService(session).read(tenant_id, site_id, provider_key)
            config = CollectionConfiguration.model_validate(
                {
                    "policy": {**current["policy"], "actor": payload.actor},
                    "capabilities": current["capabilities"],
                }
            )
            projection = ConfigurationService(session).preview(
                tenant_id, site_id, provider_key, config
            )
            if projection["blockers"]:
                raise ValueError(" ".join(projection["blockers"]))
        policy = service.transition(
            tenant_id, site_id, provider_key, payload.action, payload.actor, payload.reason
        )
        reconcile_schedules(session, policy)
    except ValueError as exc:
        raise ApiError(409, "PROVIDER_ACTION_BLOCKED", str(exc)) from exc
    session.commit()
    return service.detail(tenant_id, site_id, provider_key)


@router.put(
    "/providers/{provider_key}/capabilities/{capability_key}",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def provider_capability_policy(
    provider_key: str,
    capability_key: str,
    payload: ProviderCapabilityInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        service.set_capability(
            tenant_id,
            site_id,
            provider_key,
            capability_key,
            payload.enabled,
            payload.cadence,
            payload.actor,
        )
    except ValueError as exc:
        raise ApiError(409, "PROVIDER_CAPABILITY_INVALID", str(exc)) from exc
    disable_partial_configuration(session, tenant_id, site_id, provider_key, payload.actor)
    session.commit()
    return service.detail(tenant_id, site_id, provider_key)


@router.post(
    "/providers/{provider_key}/capabilities/{capability_key}/targets",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def provider_target(
    provider_key: str,
    capability_key: str,
    payload: ProviderTargetInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        service.add_target(
            tenant_id,
            site_id,
            provider_key,
            capability_key,
            payload.target_type,
            payload.target_value,
            payload.priority,
            payload.actor,
        )
    except ValueError as exc:
        raise ApiError(409, "PROVIDER_TARGET_INVALID", str(exc)) from exc
    disable_partial_configuration(session, tenant_id, site_id, provider_key, payload.actor)
    session.commit()
    return service.detail(tenant_id, site_id, provider_key)


@router.put(
    "/providers/{provider_key}/targets/{target_id}",
    dependencies=[Depends(require_role(Role.ADMIN))],
)
def provider_target_status(
    provider_key: str,
    target_id: uuid.UUID,
    payload: ProviderTargetStatusInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        service.set_target_enabled(
            tenant_id, site_id, provider_key, target_id, payload.enabled, payload.actor
        )
    except ValueError as exc:
        raise ApiError(404, "PROVIDER_TARGET_NOT_FOUND", str(exc)) from exc
    disable_partial_configuration(session, tenant_id, site_id, provider_key, payload.actor)
    session.commit()
    return service.detail(tenant_id, site_id, provider_key)


@router.post(
    "/providers/{provider_key}/preflight", dependencies=[Depends(require_role(Role.ADMIN))]
)
def provider_preflight(
    provider_key: str,
    payload: ProviderPreflightInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = ProviderControlService(session)
    try:
        result = service.preflight(
            tenant_id,
            site_id,
            provider_key,
            payload.capability_key,
            payload.target_values,
            payload.estimated_requests,
            payload.estimated_units,
            payload.reserve,
        )
    except ValueError as exc:
        raise ApiError(409, "PROVIDER_PREFLIGHT_BLOCKED", str(exc)) from exc
    if payload.reserve:
        session.commit()
    return asdict(result)


def scoped(
    model: Any, resource_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session
) -> Any:
    row = session.scalar(
        select(model).where(
            model.id == resource_id, model.tenant_id == tenant_id, model.site_id == site_id
        )
    )
    if not row:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Resource not found in site scope.")
    return row


@router.get("/health", response_model=Health)
def health(session: Session = Depends(database)) -> Health:
    session.execute(select(1))
    return Health(
        status="ok",
        database="ok",
        auth_configured=bool(os.environ.get("GIS_API_OPERATOR_KEY")),
        api_version="v1",
        request_id=uuid.uuid4(),
    )


@router.get(
    "/sites", response_model=list[SiteContext], dependencies=[Depends(require_role(Role.READ))]
)
def sites(tenant_id: uuid.UUID, session: Session = Depends(database)) -> list[SiteContext]:
    rows = list(
        session.scalars(select(Site).where(Site.tenant_id == tenant_id).order_by(Site.name))
    )
    return [
        SiteContext(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            slug=row.slug,
            canonical_url=row.canonical_url,
            timezone=row.timezone,
            status=row.status.value,
        )
        for row in rows
    ]


@router.get("/sites/{site_id}/status", dependencies=[Depends(require_role(Role.READ))])
def site_status(
    site_id: uuid.UUID, tenant_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    queries = WorkbenchQueries(session)
    site = queries.site(tenant_id, site_id)
    return {
        "site": row_data(site),
        "overview": queries.overview(tenant_id, site_id),
        "capabilities": queries.capability_status(tenant_id, site_id),
    }


@router.get("/capabilities", dependencies=[Depends(require_role(Role.READ))])
def capabilities(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return WorkbenchQueries(session).capability_status(tenant_id, site_id)


@router.get("/overview", dependencies=[Depends(require_role(Role.READ))])
def overview(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return WorkbenchQueries(session).overview(tenant_id, site_id)


@router.get("/goals", dependencies=[Depends(require_role(Role.READ))])
def goals(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    lifecycle: Optional[str] = None,
    level: Optional[str] = None,
    measurement: Optional[str] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    session: Session = Depends(database),
) -> dict[str, Any]:
    statement = select(StrategicObjective).where(
        StrategicObjective.tenant_id == tenant_id, StrategicObjective.site_id == site_id
    )
    if lifecycle:
        statement = statement.where(StrategicObjective.lifecycle == lifecycle)
    if level:
        statement = statement.where(StrategicObjective.level == level)
    if measurement:
        statement = statement.where(StrategicObjective.measurement_health == measurement)
    if search:
        statement = statement.where(StrategicObjective.name.ilike(f"%{search}%"))
    rows = list(session.scalars(statement.order_by(StrategicObjective.created_at.desc())))
    items = [
        {
            **row_data(row),
            "label": row.name,
            "type": row.objective_type.value,
            "status": row.lifecycle.value,
            "measurement": row.measurement_health.value,
            "decomposition": row.decomposition_state.value,
            "href": f"/goals/{row.id}",
        }
        for row in rows[(page - 1) * limit : page * limit]
    ]
    all_rows = list(
        session.scalars(
            select(StrategicObjective).where(
                StrategicObjective.tenant_id == tenant_id,
                StrategicObjective.site_id == site_id,
            )
        )
    )
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": len(rows),
        "summary": {
            "active_business_goals": sum(
                row.level.value == "BUSINESS" and row.lifecycle.value == "ACTIVE"
                for row in all_rows
            ),
            "active_subordinate_objectives": sum(
                row.level.value != "BUSINESS" and row.lifecycle.value == "ACTIVE"
                for row in all_rows
            ),
            "measurable": sum(row.measurement_health.value == "MEASURABLE" for row in all_rows),
            "not_measurable": sum(row.measurement_health.value != "MEASURABLE" for row in all_rows),
            "awaiting_approval": sum(row.approval_state.value == "PENDING" for row in all_rows),
            "decomposition_blocked": sum(
                row.decomposition_state.value.startswith("BLOCKED") for row in all_rows
            ),
        },
    }


@router.post("/goals", dependencies=[Depends(require_role(Role.REVIEW))], status_code=201)
def create_goal(
    payload: GoalCreateInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        objective_type = ObjectiveType(payload.objective_type)
    except ValueError as exc:
        raise ApiError(422, "INVALID_GOAL_TYPE", "Unsupported business goal type.") from exc
    service = GoalService(session)
    row = service.create_goal(
        tenant_id=tenant_id,
        site_id=site_id,
        name=payload.name,
        description=payload.description,
        objective_type=objective_type,
        rationale=payload.rationale,
        priority=payload.priority,
        deadline=payload.deadline,
        actor=payload.actor,
        activate=payload.activate,
    )
    session.commit()
    return row_data(row)


@router.get("/goals/map", dependencies=[Depends(require_role(Role.READ))])
def goals_map(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    nodes = list(
        session.scalars(
            select(StrategicObjective).where(
                StrategicObjective.tenant_id == tenant_id, StrategicObjective.site_id == site_id
            )
        )
    )
    node_ids = [row.id for row in nodes]
    edges = (
        list(
            session.scalars(
                select(ObjectiveRelationship).where(
                    ObjectiveRelationship.tenant_id == tenant_id,
                    ObjectiveRelationship.source_objective_id.in_(node_ids),
                )
            )
        )
        if node_ids
        else []
    )
    return {
        "nodes": [
            {
                "id": str(row.id),
                "label": row.name,
                "level": row.level.value,
                "origin": row.origin.value,
                "lifecycle": row.lifecycle.value,
                "approval": row.approval_state.value,
                "decomposition": row.decomposition_state.value,
                "href": f"/goals/{row.id}",
            }
            for row in nodes
        ],
        "edges": [
            {
                "id": str(edge.id),
                "source": str(edge.source_objective_id),
                "target": str(edge.target_objective_id),
                "type": edge.relationship_type.value,
            }
            for edge in edges
        ],
    }


@router.get("/goals/metrics", dependencies=[Depends(require_role(Role.READ))])
def goal_metrics(
    goal_type: Optional[str] = None, session: Session = Depends(database)
) -> dict[str, Any]:
    service = GoalService(session)
    if goal_type:
        try:
            result = service.recommend_metrics(ObjectiveType(goal_type))
        except ValueError as exc:
            raise ApiError(422, "INVALID_GOAL_TYPE", "Unsupported business goal type.") from exc
        session.commit()
        return result
    rows = list(
        session.scalars(
            select(MetricDefinition)
            .where(MetricDefinition.enabled.is_(True))
            .order_by(MetricDefinition.domain, MetricDefinition.name)
        )
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "key": row.key,
                "name": row.name,
                "description": row.description,
                "domain": row.domain,
                "unit": row.unit,
                "directionality": row.directionality,
                "aggregation": row.aggregation,
                "supported_scopes": row.supported_scopes_json,
                "authoritative_source": row.source_system,
                "currently_measurable": row.currently_measurable,
                "derived": row.derived,
            }
            for row in rows
        ]
    }


@router.get("/goals/{resource_id}", dependencies=[Depends(require_role(Role.READ))])
def goal_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = GoalService(session)
    try:
        row = service._objective(resource_id, tenant_id, site_id)
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", "Goal not found in site scope.") from exc
    targets = list(
        session.scalars(select(ObjectiveTarget).where(ObjectiveTarget.objective_id == row.id))
    )
    metric_ids = [target.metric_definition_id for target in targets]
    metrics = (
        {
            metric.id: metric
            for metric in session.scalars(
                select(MetricDefinition).where(MetricDefinition.id.in_(metric_ids))
            )
        }
        if metric_ids
        else {}
    )
    derivations = list(
        session.scalars(
            select(ObjectiveDerivation)
            .where(ObjectiveDerivation.source_objective_id == row.id)
            .order_by(ObjectiveDerivation.executed_at.desc())
        )
    )
    history = list(
        session.scalars(
            select(ObjectiveAuditEvent)
            .where(ObjectiveAuditEvent.objective_id == row.id)
            .order_by(ObjectiveAuditEvent.occurred_at.desc())
        )
    )
    edges = list(
        session.scalars(
            select(ObjectiveRelationship).where(
                or_(
                    ObjectiveRelationship.source_objective_id == row.id,
                    ObjectiveRelationship.target_objective_id == row.id,
                )
            )
        )
    )
    return {
        "id": str(row.id),
        "resource_type": "goal",
        "data": {
            **row_data(row),
            "measurement_summary": {
                "metric_capability": (
                    "SUPPORTED"
                    if any(metrics[t.metric_definition_id].currently_measurable for t in targets)
                    else "UNSUPPORTED"
                )
                if targets
                else "NOT_SELECTED",
                "binding": "BOUND" if targets else "NOT_BOUND",
                "current_measurement": "AVAILABLE"
                if any(t.current_value is not None for t in targets)
                else "AWAITING_MEASUREMENT",
                "health": row.measurement_health.value,
            },
            "targets": [
                {
                    **row_data(target),
                    "metric": GoalService.metric_choice(metrics[target.metric_definition_id]),
                    "progress": GoalService.progress(target),
                    "binding_status": "BOUND" if target.measurement_binding_json else "NOT_BOUND",
                    "current_measurement_status": "AVAILABLE"
                    if target.current_value is not None
                    else "AWAITING_MEASUREMENT",
                }
                for target in targets
            ],
            "derivations": [row_data(item) for item in derivations],
            "history": [row_data(item) for item in history],
            "relationships": [row_data(item) for item in edges],
        },
    }


@router.get("/goals/{resource_id}/progress", dependencies=[Depends(require_role(Role.READ))])
def goal_progress(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        row = GoalService(session)._objective(resource_id, tenant_id, site_id)
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", str(exc)) from exc
    targets = list(
        session.scalars(select(ObjectiveTarget).where(ObjectiveTarget.objective_id == row.id))
    )
    return {
        "goal_id": str(row.id),
        "lifecycle": row.lifecycle.value,
        "progress_state": row.progress_state.value,
        "measurement_health": row.measurement_health.value,
        "feasibility_state": row.feasibility_state.value,
        "feasibility_reason": row.feasibility_reason,
        "targets": [GoalService.progress(target) for target in targets],
    }


@router.get("/goals/{resource_id}/decomposition", dependencies=[Depends(require_role(Role.READ))])
def goal_decomposition(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        row = GoalService(session)._objective(resource_id, tenant_id, site_id)
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", str(exc)) from exc
    plans = list(
        session.scalars(select(DecompositionPlan).where(DecompositionPlan.objective_id == row.id))
    )
    derivations = list(
        session.scalars(
            select(ObjectiveDerivation)
            .where(ObjectiveDerivation.source_objective_id == row.id)
            .order_by(ObjectiveDerivation.executed_at.desc())
        )
    )
    return {
        "goal_id": str(row.id),
        "state": row.decomposition_state.value,
        "plans": [row_data(plan) for plan in plans],
        "derivations": [row_data(derivation) for derivation in derivations],
    }


@router.patch("/goals/{resource_id}", dependencies=[Depends(require_role(Role.REVIEW))])
def update_goal(
    resource_id: uuid.UUID,
    payload: GoalUpdateInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = GoalService(session)
    try:
        row = service.update_goal(
            resource_id,
            tenant_id,
            site_id,
            payload.actor,
            payload.model_dump(exclude={"actor", "reason"}, exclude_unset=True),
            payload.reason,
        )
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", str(exc)) from exc
    session.commit()
    return row_data(row)


def _goal_transition(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    lifecycle: ObjectiveLifecycle,
    session: Session,
) -> dict[str, Any]:
    try:
        row = GoalService(session).transition(
            resource_id, tenant_id, site_id, lifecycle, payload.actor, payload.reason
        )
    except ValueError as exc:
        raise ApiError(409, "INVALID_GOAL_TRANSITION", str(exc)) from exc
    session.commit()
    return row_data(row)


@router.post("/goals/{resource_id}/activate", dependencies=[Depends(require_role(Role.APPROVE))])
def activate_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return _goal_transition(
        resource_id, payload, tenant_id, site_id, ObjectiveLifecycle.ACTIVE, session
    )


@router.post("/goals/{resource_id}/pause", dependencies=[Depends(require_role(Role.APPROVE))])
def pause_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return _goal_transition(
        resource_id, payload, tenant_id, site_id, ObjectiveLifecycle.PAUSED, session
    )


@router.post("/goals/{resource_id}/archive", dependencies=[Depends(require_role(Role.APPROVE))])
def archive_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return _goal_transition(
        resource_id, payload, tenant_id, site_id, ObjectiveLifecycle.ARCHIVED, session
    )


@router.post("/goals/{resource_id}/approve", dependencies=[Depends(require_role(Role.APPROVE))])
def approve_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        row = GoalService(session).approve(
            resource_id, tenant_id, site_id, payload.actor, True, payload.reason
        )
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", str(exc)) from exc
    session.commit()
    return row_data(row)


@router.post("/goals/{resource_id}/reject", dependencies=[Depends(require_role(Role.APPROVE))])
def reject_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        row = GoalService(session).approve(
            resource_id, tenant_id, site_id, payload.actor, False, payload.reason
        )
    except ValueError as exc:
        raise ApiError(404, "GOAL_NOT_FOUND", str(exc)) from exc
    session.commit()
    return row_data(row)


@router.post(
    "/goals/{resource_id}/relationships",
    dependencies=[Depends(require_role(Role.REVIEW))],
    status_code=201,
)
def add_goal_relationship(
    resource_id: uuid.UUID,
    payload: GoalRelationshipInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        edge = GoalService(session).add_relationship(
            tenant_id=tenant_id,
            site_id=site_id,
            source_id=resource_id,
            target_id=payload.target_objective_id,
            actor=payload.actor,
            relationship_type=ObjectiveRelationshipType(payload.relationship_type),
        )
    except ValueError as exc:
        raise ApiError(409, "INVALID_OBJECTIVE_RELATIONSHIP", str(exc)) from exc
    session.commit()
    return row_data(edge)


@router.post(
    "/goals/{resource_id}/targets",
    dependencies=[Depends(require_role(Role.REVIEW))],
    status_code=201,
)
def add_goal_target(
    resource_id: uuid.UUID,
    payload: GoalTargetInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    service = GoalService(session)
    try:
        objective = service._objective(resource_id, tenant_id, site_id)
        metric = session.scalar(
            select(MetricDefinition).where(
                MetricDefinition.key == payload.metric_key, MetricDefinition.enabled.is_(True)
            )
        )
        if metric is None:
            raise ValueError("metric is not registered")
        target = service.create_target(
            objective=objective,
            metric=metric,
            family=TargetFamily(payload.family),
            direction=TargetDirection(payload.direction),
            target_value=payload.target_value,
            actor=payload.actor,
            unit=payload.unit,
            condition=payload.condition,
        )
        target.target_upper_value = payload.target_upper_value
    except ValueError as exc:
        raise ApiError(422, "INVALID_TARGET", str(exc)) from exc
    session.commit()
    return row_data(target)


@router.post("/goals/{resource_id}/decompose", dependencies=[Depends(require_role(Role.REVIEW))])
def decompose_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        derivation = GoalService(session).decompose(resource_id, tenant_id, site_id, payload.actor)
    except ValueError as exc:
        session.commit()
        raise ApiError(422, "DECOMPOSITION_UNAVAILABLE", str(exc)) from exc
    session.commit()
    return row_data(derivation)


@router.post("/goals/{resource_id}/recalculate", dependencies=[Depends(require_role(Role.REVIEW))])
def recalculate_goal(
    resource_id: uuid.UUID,
    payload: DecisionInput,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return decompose_goal(resource_id, payload, tenant_id, site_id, session)


@router.get("/targets/{resource_id}", dependencies=[Depends(require_role(Role.READ))])
def target_detail(
    resource_id: uuid.UUID, tenant_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    row = session.scalar(
        select(ObjectiveTarget).where(
            ObjectiveTarget.id == resource_id, ObjectiveTarget.tenant_id == tenant_id
        )
    )
    if row is None:
        raise ApiError(404, "TARGET_NOT_FOUND", "Target not found in tenant scope.")
    return {
        "id": str(row.id),
        "resource_type": "target",
        "data": {**row_data(row), "progress": GoalService.progress(row)},
    }


@router.get("/targets/{resource_id}/measurements", dependencies=[Depends(require_role(Role.READ))])
def target_measurements(
    resource_id: uuid.UUID, tenant_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    target = session.scalar(
        select(ObjectiveTarget).where(
            ObjectiveTarget.id == resource_id, ObjectiveTarget.tenant_id == tenant_id
        )
    )
    if target is None:
        raise ApiError(404, "TARGET_NOT_FOUND", "Target not found in tenant scope.")
    rows = list(
        session.scalars(
            select(ObjectiveMeasurement)
            .where(ObjectiveMeasurement.target_id == resource_id)
            .order_by(ObjectiveMeasurement.measured_at.desc())
        )
    )
    return {"items": [row_data(row) for row in rows]}


@router.patch("/targets/{resource_id}", dependencies=[Depends(require_role(Role.APPROVE))])
def override_target(
    resource_id: uuid.UUID,
    payload: TargetOverrideInput,
    tenant_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    try:
        row = GoalService(session).override_target(
            resource_id, tenant_id, payload.value, payload.actor, payload.rationale
        )
    except ValueError as exc:
        raise ApiError(404, "TARGET_NOT_FOUND", str(exc)) from exc
    session.commit()
    return row_data(row)


@router.get(
    "/opportunities",
    response_model=Page[OpportunitySummary],
    dependencies=[Depends(require_role(Role.READ))],
)
def opportunities(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    family: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = Query(default=None, max_length=200),
    session: Session = Depends(database),
) -> Page[OpportunitySummary]:
    return WorkbenchQueries(session).opportunities(
        tenant_id,
        site_id,
        page=page,
        limit=limit,
        status=status,
        family=family,
        priority=priority,
        search=search,
    )


@router.get(
    "/opportunities/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def opportunity_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    detail = WorkbenchQueries(session).detail(
        Opportunity, resource_id, tenant_id, site_id, "opportunity"
    )
    evaluations = list(
        session.scalars(
            select(OpportunityEvaluation)
            .where(OpportunityEvaluation.opportunity_id == resource_id)
            .order_by(OpportunityEvaluation.evaluated_at.desc())
            .limit(100)
        )
    )
    detail.data["history"] = [row_data(row) for row in evaluations]
    detail.data["evidence"] = [
        row_data(row)
        for row in session.scalars(
            select(EvidencePackage)
            .join(
                OpportunityEvidence, OpportunityEvidence.evidence_package_id == EvidencePackage.id
            )
            .join(
                OpportunityEvaluation,
                OpportunityEvaluation.id == OpportunityEvidence.opportunity_evaluation_id,
            )
            .where(OpportunityEvaluation.opportunity_id == resource_id)
        )
    ]
    detail.data["recommendations"] = [
        row_data(row)
        for row in session.scalars(
            select(Recommendation).where(Recommendation.opportunity_id == resource_id)
        )
    ]
    detail.data["interventions"] = [
        row_data(row)
        for row in session.scalars(
            select(Intervention).where(Intervention.primary_opportunity_id == resource_id)
        )
    ]
    return detail


@router.post(
    "/opportunities/{resource_id}/dismiss", dependencies=[Depends(require_role(Role.REVIEW))]
)
def dismiss_opportunity(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: DecisionInput,
    session: Session = Depends(database),
) -> dict[str, Any]:
    row = scoped(Opportunity, resource_id, tenant_id, site_id, session)
    if body.expected_updated_at and row.updated_at != body.expected_updated_at:
        raise ApiError(409, "STALE_RESOURCE", "Opportunity changed after it was loaded.")
    OpportunityService(session).dismiss(row.id, body.reason or "operator dismissed", body.actor)
    session.commit()
    return {"id": row.id, "status": row.status.value}


@router.post(
    "/opportunities/{resource_id}/restore", dependencies=[Depends(require_role(Role.REVIEW))]
)
def restore_opportunity(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: DecisionInput,
    session: Session = Depends(database),
) -> dict[str, Any]:
    row = scoped(Opportunity, resource_id, tenant_id, site_id, session)
    OpportunityService(session).restore(row.id, body.actor)
    session.commit()
    return {"id": row.id, "status": row.status.value}


@router.post(
    "/opportunities/{resource_id}/recommendations",
    dependencies=[Depends(require_role(Role.REVIEW))],
)
def generate_recommendation(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: GenerationInput,
    session: Session = Depends(database),
) -> dict[str, Any]:
    row = scoped(Opportunity, resource_id, tenant_id, site_id, session)
    result = RecommendationService(session, FixtureRecommendationProvider()).generate(
        row.id, dry_run=body.dry_run, force=body.force
    )
    session.rollback() if body.dry_run else session.commit()
    return {
        **result,
        "provider_label": "Fixture / development recommendation provider",
        "production_ai": False,
    }


@router.get("/recommendations", dependencies=[Depends(require_role(Role.READ))])
def recommendations(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(database),
) -> dict[str, Any]:
    return WorkbenchQueries(session).simple_page(Recommendation, tenant_id, site_id, page, limit)


@router.get(
    "/recommendations/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def recommendation_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    detail = WorkbenchQueries(session).detail(
        Recommendation, resource_id, tenant_id, site_id, "recommendation"
    )
    detail.data["candidates"] = [
        row_data(row)
        for row in session.scalars(
            select(RecommendationCandidate)
            .where(RecommendationCandidate.recommendation_id == resource_id)
            .order_by(RecommendationCandidate.rank)
        )
    ]
    detail.data["history"] = [
        row_data(row)
        for row in session.scalars(
            select(RecommendationReview)
            .where(RecommendationReview.recommendation_id == resource_id)
            .order_by(RecommendationReview.reviewed_at)
        )
    ]
    detail.data["evidence"] = [
        row_data(row)
        for row in session.scalars(
            select(EvidencePackage)
            .join(
                RecommendationEvidence,
                RecommendationEvidence.evidence_package_id == EvidencePackage.id,
            )
            .where(RecommendationEvidence.recommendation_id == resource_id)
        )
    ]
    detail.data["acceptance_is_approval"] = False
    return detail


def review_recommendation(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: RecommendationReviewInput,
    decision: RecommendationReviewDecision,
    session: Session,
) -> dict[str, Any]:
    row = scoped(Recommendation, resource_id, tenant_id, site_id, session)
    if body.expected_updated_at and row.updated_at != body.expected_updated_at:
        raise ApiError(409, "STALE_RESOURCE", "Recommendation changed after it was loaded.")
    try:
        RecommendationService(session, FixtureRecommendationProvider()).review(
            row.id, decision, body.actor, body.candidate_ids, reason=body.reason
        )
        session.commit()
    except ValueError as error:
        session.rollback()
        raise ApiError(422, "RECOMMENDATION_REVIEW_INVALID", str(error)) from error
    interventions = list(
        session.scalars(
            select(Intervention).where(Intervention.primary_opportunity_id == row.opportunity_id)
        )
    )
    return {
        "id": row.id,
        "status": row.status.value,
        "interventions": [{"id": item.id, "status": item.status.value} for item in interventions],
        "intervention_approved": False,
    }


@router.post(
    "/recommendations/{resource_id}/accept", dependencies=[Depends(require_role(Role.REVIEW))]
)
def accept_recommendation(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: RecommendationReviewInput,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return review_recommendation(
        resource_id, tenant_id, site_id, body, RecommendationReviewDecision.ACCEPT, session
    )


@router.post(
    "/recommendations/{resource_id}/reject", dependencies=[Depends(require_role(Role.REVIEW))]
)
def reject_recommendation(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: RecommendationReviewInput,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return review_recommendation(
        resource_id, tenant_id, site_id, body, RecommendationReviewDecision.REJECT, session
    )


@router.get("/interventions", dependencies=[Depends(require_role(Role.READ))])
def interventions(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(database),
) -> dict[str, Any]:
    return WorkbenchQueries(session).simple_page(Intervention, tenant_id, site_id, page, limit)


@router.get(
    "/interventions/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def intervention_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    detail = WorkbenchQueries(session).detail(
        Intervention, resource_id, tenant_id, site_id, "intervention"
    )
    detail.data["history"] = [
        row_data(row)
        for row in session.scalars(
            select(InterventionLifecycleEvent)
            .where(InterventionLifecycleEvent.intervention_id == resource_id)
            .order_by(InterventionLifecycleEvent.occurred_at)
        )
    ]
    detail.data["hypotheses"] = [
        row_data(row)
        for row in session.scalars(
            select(InterventionHypothesis).where(
                InterventionHypothesis.intervention_id == resource_id
            )
        )
    ]
    detail.data["measurement"] = [
        row_data(row)
        for row in session.scalars(
            select(MeasurementContract).where(MeasurementContract.intervention_id == resource_id)
        )
    ]
    detail.data["outcomes"] = [
        row_data(row)
        for row in session.scalars(
            select(InterventionOutcome).where(InterventionOutcome.intervention_id == resource_id)
        )
    ]
    return detail


def transition(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    body: DecisionInput,
    target: InterventionStatus,
    session: Session,
) -> dict[str, Any]:
    row = scoped(Intervention, resource_id, tenant_id, site_id, session)
    if body.expected_updated_at and row.updated_at != body.expected_updated_at:
        raise ApiError(409, "STALE_RESOURCE", "Intervention changed after it was loaded.")
    try:
        InterventionService(session).transition(
            row.id, target, actor=body.actor, reason=body.reason
        )
        session.commit()
    except ValueError as error:
        session.rollback()
        raise ApiError(409, "INVALID_LIFECYCLE_TRANSITION", str(error)) from error
    return {"id": row.id, "status": row.status.value}


def transition_endpoint(target: InterventionStatus):  # type: ignore[no-untyped-def]
    def endpoint(
        resource_id: uuid.UUID,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        body: DecisionInput,
        session: Session = Depends(database),
    ) -> dict[str, Any]:
        return transition(resource_id, tenant_id, site_id, body, target, session)

    return endpoint


for action, target, role in (
    ("propose", InterventionStatus.PROPOSED, Role.REVIEW),
    ("approve", InterventionStatus.APPROVED, Role.APPROVE),
    ("reject", InterventionStatus.REJECTED, Role.APPROVE),
    ("start", InterventionStatus.IN_PROGRESS, Role.APPROVE),
    ("complete", InterventionStatus.COMPLETED, Role.APPROVE),
    ("cancel", InterventionStatus.CANCELLED, Role.APPROVE),
):
    router.add_api_route(
        f"/interventions/{{resource_id}}/{action}",
        transition_endpoint(target),
        methods=["POST"],
        dependencies=[Depends(require_role(role))],
    )


@router.get("/evidence/packages", dependencies=[Depends(require_role(Role.READ))])
def evidence_packages(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    entity_type: Optional[str] = None,
    sufficiency: Optional[str] = None,
    source: Optional[str] = None,
    sort: str = Query("updated", pattern="^(name|updated|status|freshness)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    return evidence_inventory(
        session,
        tenant_id,
        site_id,
        page=page,
        limit=limit,
        search=search,
        entity_type=entity_type,
        sufficiency=sufficiency,
        source=source,
        sort=sort,
        order=order,
    )


@router.get(
    "/evidence/packages/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def evidence_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    data = semantic_evidence_detail(session, resource_id, tenant_id, site_id)
    return ResourceDetail(
        id=resource_id,
        tenant_id=tenant_id,
        site_id=site_id,
        resource_type="evidence_package",
        data=data,
    )


@router.get("/evidence/gaps/{resource_id}", dependencies=[Depends(require_role(Role.READ))])
def evidence_gap(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    return evidence_gap_detail(session, resource_id, tenant_id, site_id)


@router.get("/markets", dependencies=[Depends(require_role(Role.READ))])
def markets(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(database),
) -> dict[str, Any]:
    result = WorkbenchQueries(session).simple_page(
        MarketDefinition, tenant_id, site_id, page, limit
    )
    result["items"] = [
        {
            **item,
            "label": item["name"],
            "type": item["market_type"],
            "href": f"/markets/{item['id']}",
        }
        for item in result["items"]
    ]
    return result


@router.get(
    "/markets/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def market_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    data = semantic_market_detail(session, resource_id, tenant_id, site_id)
    return ResourceDetail(
        id=resource_id, tenant_id=tenant_id, site_id=site_id, resource_type="market", data=data
    )


@router.get("/collection", dependencies=[Depends(require_role(Role.READ))])
def collection(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(default=None, max_length=200),
    target_type: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = Query("updated", pattern="^(name|updated|status|type)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    return collection_inventory(
        session,
        tenant_id,
        site_id,
        page=page,
        limit=limit,
        search=search,
        target_type=target_type,
        status=status,
        sort=sort,
        order=order,
    )


@router.get("/collection/{resource_id}", dependencies=[Depends(require_role(Role.READ))])
def collection_target_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    return semantic_collection_detail(session, resource_id, tenant_id, site_id)


@router.get("/opportunity-evaluations", dependencies=[Depends(require_role(Role.READ))])
def opportunity_evaluation_summary(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    return opportunity_diagnostics(session, tenant_id, site_id)


@router.get("/experiments", dependencies=[Depends(require_role(Role.READ))])
def experiments(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(database),
) -> dict[str, Any]:
    return WorkbenchQueries(session).simple_page(Experiment, tenant_id, site_id, page, limit)


@router.get(
    "/experiments/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def experiment_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    detail = WorkbenchQueries(session).detail(
        Experiment, resource_id, tenant_id, site_id, "experiment"
    )
    intervention_id = uuid.UUID(str(detail.data["intervention_id"]))
    intervention = session.get(Intervention, intervention_id)
    detail.data["intervention"] = row_data(intervention) if intervention else None
    detail.data["outcomes"] = [
        row_data(row)
        for row in session.scalars(
            select(InterventionOutcome).where(
                InterventionOutcome.intervention_id == intervention_id
            )
        )
    ]
    return detail


@router.get("/outcomes", dependencies=[Depends(require_role(Role.READ))])
def outcomes(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(database),
) -> dict[str, Any]:
    WorkbenchQueries(session).site(tenant_id, site_id)
    query = (
        select(InterventionOutcome)
        .join(Intervention)
        .where(Intervention.tenant_id == tenant_id, Intervention.site_id == site_id)
    )
    total = (
        session.scalar(
            select(func.count())
            .select_from(InterventionOutcome)
            .join(Intervention)
            .where(Intervention.tenant_id == tenant_id, Intervention.site_id == site_id)
        )
        or 0
    )
    rows = list(session.scalars(query.offset((page - 1) * limit).limit(limit)))
    return {
        "items": [
            {**row_data(row), "semantic_label": "OBSERVED_CHANGE", "causal_impact": False}
            for row in rows
        ],
        "page": page,
        "limit": limit,
        "total": total,
    }


@router.get(
    "/outcomes/{resource_id}",
    response_model=ResourceDetail,
    dependencies=[Depends(require_role(Role.READ))],
)
def outcome_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> ResourceDetail:
    WorkbenchQueries(session).site(tenant_id, site_id)
    row = session.scalar(
        select(InterventionOutcome)
        .join(Intervention)
        .where(
            InterventionOutcome.id == resource_id,
            Intervention.tenant_id == tenant_id,
            Intervention.site_id == site_id,
        )
    )
    if not row:
        raise ApiError(404, "OUTCOME_NOT_FOUND", "Outcome not found in site scope.")
    data = {**row_data(row), "semantic_label": "OBSERVED_CHANGE", "causal_impact": False}
    return ResourceDetail(
        id=row.id, tenant_id=tenant_id, site_id=site_id, resource_type="outcome", data=data
    )


@router.get("/system/pipelines", dependencies=[Depends(require_role(Role.READ))])
def system_pipelines(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return SystemQueries(session).pipelines(tenant_id, site_id)


@router.get("/system/pipelines/{pipeline_key}", dependencies=[Depends(require_role(Role.READ))])
def system_pipeline_detail(
    pipeline_key: str,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return SystemQueries(session).pipeline_detail(pipeline_key, tenant_id, site_id)


@router.get("/system/runs", dependencies=[Depends(require_role(Role.READ))])
def system_runs(
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: Optional[str] = None,
    pipeline_key: Optional[str] = None,
    provider_key: Optional[str] = None,
    trigger: Optional[str] = None,
    timeliness: Optional[str] = None,
    outcome: Optional[str] = None,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return SystemQueries(session).runs(
        tenant_id,
        site_id,
        page=page,
        limit=limit,
        status=status,
        pipeline_key=pipeline_key,
        provider_key=provider_key,
        trigger=trigger,
        timeliness=timeliness,
        outcome=outcome,
    )


@router.get("/system/runs/{resource_id}", dependencies=[Depends(require_role(Role.READ))])
def system_run_detail(
    resource_id: uuid.UUID,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return SystemQueries(session).run_detail(resource_id, tenant_id, site_id)


@router.get("/system/sources", dependencies=[Depends(require_role(Role.READ))])
def system_sources(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return SystemQueries(session).sources(tenant_id, site_id)


@router.get("/system/sources/{source_key}", dependencies=[Depends(require_role(Role.READ))])
def system_source_detail(
    source_key: str,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    session: Session = Depends(database),
) -> dict[str, Any]:
    return SystemQueries(session).source_detail(source_key, tenant_id, site_id)


@router.get("/system/data-flow", dependencies=[Depends(require_role(Role.READ))])
def system_data_flow(
    tenant_id: uuid.UUID, site_id: uuid.UUID, session: Session = Depends(database)
) -> dict[str, Any]:
    return SystemQueries(session).data_flow(tenant_id, site_id)
