from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.api.auth import Role, require_role
from gis.api.errors import ApiError
from gis.api.schemas import (
    DecisionInput,
    GenerationInput,
    Health,
    OpportunitySummary,
    Page,
    RecommendationReviewInput,
    ResourceDetail,
    SiteContext,
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
from gis.interventions.service import InterventionService
from gis.models import (
    EvidencePackage,
    Experiment,
    Intervention,
    InterventionHypothesis,
    InterventionLifecycleEvent,
    InterventionOutcome,
    InterventionStatus,
    MarketDefinition,
    MeasurementContract,
    Opportunity,
    OpportunityEvaluation,
    OpportunityEvidence,
    Recommendation,
    RecommendationCandidate,
    RecommendationEvidence,
    RecommendationReview,
    RecommendationReviewDecision,
    Site,
)
from gis.opportunities.service import OpportunityService
from gis.recommendations.provider import FixtureRecommendationProvider
from gis.recommendations.service import RecommendationService

router = APIRouter(prefix="/api/v1")


def database() -> Session:  # type: ignore[misc]
    with session_factory()() as session:
        yield session


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
    session: Session = Depends(database),
) -> dict[str, Any]:
    return SystemQueries(session).runs(
        tenant_id, site_id, page=page, limit=limit, status=status, pipeline_key=pipeline_key
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
