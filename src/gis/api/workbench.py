from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from gis.api.errors import ApiError
from gis.api.schemas import OpportunitySummary, Page, ResourceDetail
from gis.models import (
    AnalyticalEntity,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionTarget,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    Experiment,
    FreshnessState,
    Intervention,
    InterventionOutcome,
    MarketDefinition,
    MarketDefinitionMember,
    Opportunity,
    PipelineDefinition,
    Recommendation,
    ScheduleDefinition,
    Site,
)


def encoded(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (uuid.UUID, datetime)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def row_data(row: Any, *, exclude: Optional[set[str]] = None) -> dict[str, Any]:
    exclude = exclude or set()
    return {
        attribute.key: encoded(getattr(row, attribute.key))
        for attribute in row.__mapper__.column_attrs
        if attribute.key not in exclude
    }


class WorkbenchQueries:
    def __init__(self, session: Session) -> None:
        self.session = session

    def site(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> Site:
        row = self.session.scalar(
            select(Site).where(Site.id == site_id, Site.tenant_id == tenant_id)
        )
        if not row:
            raise ApiError(404, "SITE_NOT_FOUND", "Site not found in tenant scope.")
        return row

    def opportunities(
        self,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        *,
        page: int,
        limit: int,
        status: Optional[str],
        family: Optional[str],
        priority: Optional[str],
        search: Optional[str],
    ) -> Page[OpportunitySummary]:
        self.site(tenant_id, site_id)
        filters: list[Any] = [Opportunity.tenant_id == tenant_id, Opportunity.site_id == site_id]
        if status:
            filters.append(Opportunity.status == status)
        if family:
            filters.append(Opportunity.family == family)
        if priority:
            filters.append(Opportunity.priority == priority)
        if search:
            filters.append(
                or_(
                    Opportunity.title.ilike(f"%{search}%"),
                    AnalyticalEntity.canonical_key.ilike(f"%{search}%"),
                )
            )
        total = (
            self.session.scalar(
                select(func.count()).select_from(Opportunity).join(AnalyticalEntity).where(*filters)
            )
            or 0
        )
        rows = self.session.execute(
            select(Opportunity, AnalyticalEntity)
            .join(AnalyticalEntity, AnalyticalEntity.id == Opportunity.analytical_entity_id)
            .where(*filters)
            .order_by(Opportunity.priority, Opportunity.detected_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        ).all()
        items: list[OpportunitySummary] = []
        for opportunity, entity in rows:
            recommendation = self.session.scalar(
                select(Recommendation.status)
                .where(Recommendation.opportunity_id == opportunity.id)
                .order_by(Recommendation.created_at.desc())
                .limit(1)
            )
            intervention = self.session.scalar(
                select(Intervention.status)
                .where(Intervention.primary_opportunity_id == opportunity.id)
                .order_by(Intervention.created_at.desc())
                .limit(1)
            )
            items.append(
                OpportunitySummary(
                    id=opportunity.id,
                    tenant_id=opportunity.tenant_id,
                    site_id=opportunity.site_id,
                    title=opportunity.title,
                    family=opportunity.family.value,
                    opportunity_type=opportunity.opportunity_type,
                    status=opportunity.status.value,
                    priority=opportunity.priority.value,
                    evidence_sufficiency=opportunity.evidence_sufficiency.value,
                    entity_id=entity.id,
                    entity_type=entity.entity_type.value,
                    entity_key=entity.canonical_key,
                    detected_at=opportunity.detected_at,
                    updated_at=opportunity.updated_at,
                    materiality=opportunity.materiality_json,
                    limitations=opportunity.limitations_json,
                    recommendation_status=recommendation.value if recommendation else None,
                    intervention_status=intervention.value if intervention else None,
                )
            )
        return Page(items=items, page=page, limit=limit, total=total)

    def detail(
        self,
        model: Any,
        resource_id: uuid.UUID,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        resource_type: str,
    ) -> ResourceDetail:
        self.site(tenant_id, site_id)
        row = self.session.scalar(
            select(model).where(
                model.id == resource_id, model.tenant_id == tenant_id, model.site_id == site_id
            )
        )
        if not row:
            raise ApiError(
                404,
                f"{resource_type.upper()}_NOT_FOUND",
                f"{resource_type.title()} not found in site scope.",
            )
        return ResourceDetail(
            id=row.id,
            tenant_id=tenant_id,
            site_id=site_id,
            resource_type=resource_type,
            data=row_data(row),
        )

    def evidence(
        self, package_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> ResourceDetail:
        detail = self.detail(EvidencePackage, package_id, tenant_id, site_id, "evidence_package")
        dimensions = list(
            self.session.scalars(
                select(EvidenceQualityDimension).where(
                    EvidenceQualityDimension.evidence_package_id == package_id
                )
            )
        )
        items = list(
            self.session.scalars(
                select(EvidencePackageItem).where(
                    EvidencePackageItem.evidence_package_id == package_id
                )
            )
        )
        gaps = list(
            self.session.scalars(
                select(EvidenceGap).where(EvidenceGap.evidence_package_id == package_id)
            )
        )
        detail.data.update(
            dimensions=[row_data(item) for item in dimensions],
            evidence_items=[row_data(item) for item in items],
            gaps=[row_data(item) for item in gaps],
        )
        return detail

    def simple_page(
        self, model: Any, tenant_id: uuid.UUID, site_id: uuid.UUID, page: int, limit: int
    ) -> dict[str, Any]:
        self.site(tenant_id, site_id)
        filters = [model.tenant_id == tenant_id, model.site_id == site_id]
        total = self.session.scalar(select(func.count()).select_from(model).where(*filters)) or 0
        rows = list(
            self.session.scalars(
                select(model).where(*filters).offset((page - 1) * limit).limit(limit)
            )
        )
        return {
            "items": [row_data(row) for row in rows],
            "page": page,
            "limit": limit,
            "total": total,
        }

    def overview(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self.site(tenant_id, site_id)

        def count(model: Any, *conditions: Any) -> int:
            return (
                self.session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.tenant_id == tenant_id, model.site_id == site_id, *conditions)
                )
                or 0
            )

        return {
            "opportunities_to_review": count(
                Opportunity, Opportunity.status.in_(["ACTIVE", "WATCHING"])
            ),
            "recommendations_to_review": count(
                Recommendation, Recommendation.status == "READY_FOR_REVIEW"
            ),
            "interventions_to_approve": count(
                Intervention, Intervention.status.in_(["DRAFT", "PROPOSED"])
            ),
            "active_interventions": count(
                Intervention, Intervention.status.in_(["APPROVED", "SCHEDULED", "IN_PROGRESS"])
            ),
            "experiments_running": count(Experiment, Experiment.status == "RUNNING"),
            "recent_outcomes": self.session.scalar(
                select(func.count())
                .select_from(InterventionOutcome)
                .join(Intervention)
                .where(Intervention.tenant_id == tenant_id, Intervention.site_id == site_id)
            )
            or 0,
            "unknown_values_are_zero": False,
        }

    def capability_status(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self.site(tenant_id, site_id)
        schedules = list(
            self.session.execute(
                select(ScheduleDefinition, FreshnessState, PipelineDefinition)
                .outerjoin(FreshnessState, FreshnessState.schedule_id == ScheduleDefinition.id)
                .join(PipelineDefinition, PipelineDefinition.id == ScheduleDefinition.pipeline_id)
                .where(
                    ScheduleDefinition.tenant_id == tenant_id, ScheduleDefinition.site_id == site_id
                )
            ).all()
        )
        return {
            "items": [
                {
                    "schedule": row.name,
                    "status": row.status.value,
                    "latest_success": encoded(fresh.last_successful_at) if fresh else None,
                    "stale_since": encoded(fresh.stale_since) if fresh else None,
                    "reason": (
                        "Intentionally disabled: this pipeline can consume paid provider credits."
                        if row.status.value == "DISABLED" and pipeline.paid_provider
                        else "Disabled pending safe operator configuration."
                        if row.status.value == "DISABLED"
                        and row.configuration_json.get("requires_operator_configuration")
                        else "Active zero-cost local processing schedule."
                        if row.status.value == "ENABLED"
                        and pipeline.handler_key
                        in {"DBT", "LOCAL_PROCESSING", "COMPETITIVE_EVENTS"}
                        else None
                    ),
                    "pipeline_key": pipeline.key,
                    "paid_provider": pipeline.paid_provider,
                }
                for row, fresh, pipeline in schedules
            ],
            "fixture_ai_provider": True,
            "production_ai_operational": False,
        }

    def market_detail(
        self, resource_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> ResourceDetail:
        detail = self.detail(MarketDefinition, resource_id, tenant_id, site_id, "market")
        members = list(
            self.session.scalars(
                select(MarketDefinitionMember).where(
                    MarketDefinitionMember.market_definition_id == resource_id
                )
            )
        )
        detail.data["members"] = [row_data(row) for row in members]
        return detail

    def collection(
        self, tenant_id: uuid.UUID, site_id: uuid.UUID, page: int, limit: int
    ) -> dict[str, Any]:
        targets = self.simple_page(CollectionTarget, tenant_id, site_id, page, limit)
        decision = self.session.scalar(
            select(CollectionPlanningDecision)
            .join(CollectionTarget, CollectionTarget.id == CollectionPlanningDecision.target_id)
            .where(CollectionTarget.tenant_id == tenant_id, CollectionTarget.site_id == site_id)
            .order_by(CollectionPlanningDecision.evaluated_at.desc())
            .limit(1)
        )
        items = (
            list(
                self.session.scalars(
                    select(CollectionPlanItem).where(CollectionPlanItem.decision_id == decision.id)
                )
            )
            if decision
            else []
        )
        targets["current_plan"] = [row_data(row) for row in items]
        targets["schedules_activated"] = False
        return targets
