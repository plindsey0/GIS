from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from gis.api.errors import ApiError
from gis.api.schemas import OpportunitySummary, Page, ResourceDetail
from gis.models import (
    AnalyticalEntity,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionTarget,
    CompetitiveContentObservation,
    CompetitiveEvent,
    DataRightsPolicy,
    DemandAnalysisRun,
    DemandObservation,
    DemandSignal,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    Experiment,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    FreshnessState,
    GA4EventObservation,
    GA4LandingPageObservation,
    GSCSearchObservation,
    Intervention,
    InterventionOutcome,
    MarketDefinition,
    MarketDefinitionMember,
    MarketObservation,
    MarketParticipantObservation,
    Opportunity,
    PermittedUse,
    PipelineDefinition,
    Recommendation,
    ScheduleDefinition,
    SerpObservation,
    SerpResult,
    Site,
    TechnologyDetection,
    TechnologyObservation,
)
from gis.provenance.service import evaluate_policy_use


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

        def current_count(model: Any) -> int:
            conditions = [model.tenant_id == tenant_id, model.site_id == site_id]
            if hasattr(model, "effective_end"):
                conditions.append(model.effective_end.is_(None))
            return (
                self.session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0
            )

        def latest(model: Any, column: Any) -> Any:
            conditions = [model.tenant_id == tenant_id, model.site_id == site_id]
            if hasattr(model, "effective_end"):
                conditions.append(model.effective_end.is_(None))
            return encoded(self.session.scalar(select(func.max(column)).where(*conditions)))

        def source_rights(model: Any) -> tuple[bool, str | None]:
            policy_ids = set(
                self.session.scalars(
                    select(model.rights_policy_id).where(
                        model.tenant_id == tenant_id,
                        model.site_id == site_id,
                        *(
                            [model.effective_end.is_(None)]
                            if hasattr(model, "effective_end")
                            else []
                        ),
                    )
                )
            )
            if not policy_ids:
                return False, "No governed source observations are stored."
            blocked: list[str] = []
            for policy_id in policy_ids:
                policy = self.session.get(DataRightsPolicy, policy_id)
                for use in (
                    PermittedUse.AGGREGATE_STATISTICS,
                    PermittedUse.CUSTOMER_FACING_DISPLAY,
                ):
                    decision = evaluate_policy_use(self.session, policy, use)
                    if decision.status.value != "ALLOWED":
                        blocked.append(
                            f"{policy.name if policy else policy_id}: {use.value}={decision.status.value}"
                        )
            return not blocked, "; ".join(sorted(set(blocked))) or None

        gsc_count = current_count(GSCSearchObservation)
        gsc_allowed, gsc_blocker = source_rights(GSCSearchObservation)
        ga4_count = current_count(GA4EventObservation)
        ga4_allowed, ga4_blocker = source_rights(GA4EventObservation)
        serp_count = current_count(SerpObservation)
        serp_allowed, serp_blocker = source_rights(SerpObservation)
        demand_count = current_count(DemandObservation)
        external_count = current_count(ExternalSearchObservation)
        external_allowed, external_blocker = source_rights(ExternalSearchObservation)

        search_metrics = {
            "stored_observations": gsc_count,
            "latest_observation": latest(GSCSearchObservation, GSCSearchObservation.observed_at),
            "rights_state": "USABLE" if gsc_allowed else "UNKNOWN",
            "blocker": gsc_blocker,
            "clicks": None,
            "impressions": None,
            "ctr": None,
            "average_position": None,
            "observed_query_count": None,
        }
        if gsc_allowed:
            filters = [
                GSCSearchObservation.tenant_id == tenant_id,
                GSCSearchObservation.site_id == site_id,
                GSCSearchObservation.effective_end.is_(None),
            ]
            clicks, impressions, position, queries = self.session.execute(
                select(
                    func.sum(GSCSearchObservation.clicks),
                    func.sum(GSCSearchObservation.impressions),
                    func.avg(GSCSearchObservation.position),
                    func.count(distinct(GSCSearchObservation.query_hash)),
                ).where(*filters)
            ).one()
            search_metrics.update(
                clicks=encoded(clicks),
                impressions=encoded(impressions),
                ctr=encoded(clicks / impressions) if impressions else None,
                average_position=encoded(position),
                observed_query_count=queries,
            )

        traffic_metrics = {
            "stored_event_observations": ga4_count,
            "stored_landing_page_observations": current_count(GA4LandingPageObservation),
            "latest_observation": latest(GA4EventObservation, GA4EventObservation.observed_at),
            "rights_state": "USABLE" if ga4_allowed else "UNKNOWN",
            "blocker": ga4_blocker,
            "events": None,
            "users": None,
            "sessions": None,
        }
        if ga4_allowed:
            base = [
                GA4EventObservation.tenant_id == tenant_id,
                GA4EventObservation.site_id == site_id,
                GA4EventObservation.effective_end.is_(None),
            ]
            events, users = self.session.execute(
                select(
                    func.sum(GA4EventObservation.event_count),
                    func.sum(GA4EventObservation.total_users),
                ).where(*base)
            ).one()
            sessions = self.session.scalar(
                select(func.sum(GA4LandingPageObservation.sessions)).where(
                    GA4LandingPageObservation.tenant_id == tenant_id,
                    GA4LandingPageObservation.site_id == site_id,
                    GA4LandingPageObservation.effective_end.is_(None),
                )
            )
            traffic_metrics.update(
                events=encoded(events), users=encoded(users), sessions=encoded(sessions)
            )

        market = self.session.scalar(
            select(MarketDefinition)
            .where(
                MarketDefinition.tenant_id == tenant_id,
                MarketDefinition.site_id == site_id,
                MarketDefinition.status == "ACTIVE",
            )
            .order_by(MarketDefinition.version.desc())
            .limit(1)
        )
        target_types = {
            encoded(target_type): total
            for target_type, total in self.session.execute(
                select(CollectionTarget.target_type, func.count())
                .where(
                    CollectionTarget.tenant_id == tenant_id,
                    CollectionTarget.site_id == site_id,
                )
                .group_by(CollectionTarget.target_type)
            ).all()
        }
        collection_total = count(CollectionTarget)
        competitive_events = count(CompetitiveEvent)
        competitive_content = current_count(CompetitiveContentObservation)
        technology_observations = current_count(TechnologyObservation)

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
            "search": search_metrics,
            "traffic": traffic_metrics,
            "visibility": {
                "stored_serp_observations": serp_count,
                "stored_serp_results": self.session.scalar(
                    select(func.count())
                    .select_from(SerpResult)
                    .join(SerpObservation)
                    .where(
                        SerpObservation.tenant_id == tenant_id,
                        SerpObservation.site_id == site_id,
                        SerpObservation.effective_end.is_(None),
                    )
                )
                or 0,
                "latest_observation": latest(SerpObservation, SerpObservation.observed_at),
                "rights_state": "USABLE" if serp_allowed else "UNKNOWN",
                "blocker": serp_blocker,
                "tracked_query_count": None if not serp_allowed else serp_count,
            },
            "market": {
                "id": str(market.id) if market else None,
                "name": market.name if market else None,
                "version": market.version if market else None,
                "definition_member_count": self.session.scalar(
                    select(func.count())
                    .select_from(MarketDefinitionMember)
                    .where(MarketDefinitionMember.market_definition_id == market.id)
                )
                if market
                else 0,
                "observation_count": count(MarketObservation),
                "participant_count": self.session.scalar(
                    select(func.count())
                    .select_from(MarketParticipantObservation)
                    .join(MarketObservation)
                    .where(
                        MarketObservation.tenant_id == tenant_id,
                        MarketObservation.site_id == site_id,
                        MarketObservation.effective_end.is_(None),
                    )
                )
                or 0,
            },
            "demand": {
                "stored_external_keywords": self.session.scalar(
                    select(func.count())
                    .select_from(ExternalKeywordRanking)
                    .join(ExternalSearchObservation)
                    .where(
                        ExternalSearchObservation.tenant_id == tenant_id,
                        ExternalSearchObservation.site_id == site_id,
                        ExternalSearchObservation.effective_end.is_(None),
                    )
                )
                or 0,
                "stored_external_observations": external_count,
                "demand_observations": demand_count,
                "demand_signals": self.session.scalar(
                    select(func.count())
                    .select_from(DemandSignal)
                    .join(DemandAnalysisRun)
                    .where(
                        DemandAnalysisRun.tenant_id == tenant_id,
                        DemandAnalysisRun.site_id == site_id,
                    )
                )
                or 0,
                "latest_provider_observation": latest(
                    ExternalSearchObservation, ExternalSearchObservation.observed_at
                ),
                "rights_state": "USABLE" if external_allowed else "UNKNOWN",
                "blocker": external_blocker,
                "provider_specific_volume": None,
            },
            "evidence": {
                "packages": count(EvidencePackage),
                "gaps": self.session.scalar(
                    select(func.count())
                    .select_from(EvidenceGap)
                    .join(EvidencePackage)
                    .where(
                        EvidencePackage.tenant_id == tenant_id, EvidencePackage.site_id == site_id
                    )
                )
                or 0,
                "status": "NOT_PRODUCED" if count(EvidencePackage) == 0 else "AVAILABLE",
                "explanation": external_blocker
                or "No qualifying demand signals have been produced.",
            },
            "competitive": {
                "content_observations": competitive_content,
                "technology_observations": technology_observations,
                "technology_detections": self.session.scalar(
                    select(func.count())
                    .select_from(TechnologyDetection)
                    .join(TechnologyObservation)
                    .where(
                        TechnologyObservation.tenant_id == tenant_id,
                        TechnologyObservation.site_id == site_id,
                        TechnologyObservation.effective_end.is_(None),
                    )
                )
                or 0,
                "events": competitive_events,
                "latest_event": encoded(
                    self.session.scalar(
                        select(func.max(CompetitiveEvent.event_time)).where(
                            CompetitiveEvent.tenant_id == tenant_id,
                            CompetitiveEvent.site_id == site_id,
                        )
                    )
                ),
                "rights_state": "USABLE",
            },
            "collection_health": {
                "targets": collection_total,
                "query_targets": target_types.get("QUERY", 0),
                "domain_targets": target_types.get("DOMAIN", 0),
                "url_targets": target_types.get("URL", 0),
                "latest_update": encoded(
                    self.session.scalar(
                        select(func.max(CollectionTarget.updated_at)).where(
                            CollectionTarget.tenant_id == tenant_id,
                            CollectionTarget.site_id == site_id,
                        )
                    )
                ),
            },
            "unknown_values_are_zero": False,
        }

    def capability_status(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
        self.site(tenant_id, site_id)
        disabled_reasons = {
            "gsc": "Governance blocked: stored GSC evidence uses an unreviewed rights policy; retrieval remains disabled until rights and credentials are both validated.",
            "ga4": "Governance blocked: stored GA4 evidence uses an unreviewed rights policy; retrieval remains disabled until rights and credentials are both validated.",
            "experience": "Not configured: PageSpeed/CrUX quota and credentials have not been validated for unattended zero-cost collection.",
            "competitive_content": "Intentionally disabled: this collector performs new external HTTP retrieval; stored content is still available to local dbt and event processing.",
            "competitive_technology": "Intentionally disabled: this collector performs new external retrieval; stored detections remain available to local processing.",
            "market_intelligence": "Governance blocked: local synthesis requires stored SERP/external-search evidence whose aggregation rights remain UNKNOWN.",
            "intervention_measurement": "Not applicable yet: there are no approved interventions or measurement contracts to process.",
            "ai_recommendations": "Not applicable yet: there are no qualifying opportunities; external LLM providers remain unconfigured.",
        }
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
                        else disabled_reasons.get(pipeline.key)
                        if row.status.value == "DISABLED" and pipeline.key in disabled_reasons
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
