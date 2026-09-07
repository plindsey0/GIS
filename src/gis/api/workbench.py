from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.orm import Session

from gis.api.errors import ApiError
from gis.api.schemas import OpportunitySummary, Page, ResourceDetail
from gis.intelligence.service import EvidencePacketService, IntelligenceValidationError
from gis.models import (
    AnalyticalEntity,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionTarget,
    CompetitiveContentObservation,
    CompetitiveEvent,
    DataRightsPolicy,
    DataSourceConnection,
    DemandAnalysisRun,
    DemandObservation,
    DemandSignal,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    ExecutorHeartbeat,
    ExecutorRole,
    ExperienceMeasurementType,
    ExperienceObservation,
    Experiment,
    ExperimentProposal,
    ExperimentProposalEvidence,
    ExperimentProposalReview,
    ExternalKeywordRanking,
    ExternalSearchObservation,
    FreshnessState,
    GA4EventObservation,
    GA4LandingPageObservation,
    GSCSearchObservation,
    Intervention,
    InterventionOutcome,
    LLMOpportunityDetail,
    LLMRecommendationDetail,
    LLMRun,
    MarketDefinition,
    MarketDefinitionMember,
    MarketObservation,
    MarketParticipantObservation,
    ObligationStatus,
    Opportunity,
    OpportunityEvaluation,
    OpportunityEvidence,
    OpportunityReview,
    OrchestrationObligation,
    OrchestrationRun,
    PermittedUse,
    PipelineDefinition,
    Recommendation,
    RecommendationEvidence,
    RecommendationOpportunity,
    RecommendationReview,
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
                .outerjoin(RecommendationOpportunity,
                           RecommendationOpportunity.recommendation_id == Recommendation.id)
                .where(or_(Recommendation.opportunity_id == opportunity.id,
                           RecommendationOpportunity.opportunity_id == opportunity.id))
                .order_by(Recommendation.created_at.desc())
                .limit(1)
            )
            review = self.session.scalar(select(OpportunityReview.decision).where(
                OpportunityReview.opportunity_id == opportunity.id
            ).order_by(OpportunityReview.reviewed_at.desc()).limit(1))
            governed = self.session.scalar(select(LLMOpportunityDetail.id).where(
                LLMOpportunityDetail.opportunity_id == opportunity.id)) is not None
            proposal_status = self.session.scalar(select(ExperimentProposal.status)
                .join(RecommendationOpportunity,
                      RecommendationOpportunity.recommendation_id == ExperimentProposal.recommendation_id)
                .where(RecommendationOpportunity.opportunity_id == opportunity.id)
                .order_by(ExperimentProposal.created_at.desc()).limit(1))
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
                    review_state=review,
                    recommendation_state=recommendation.value if recommendation else None,
                    experiment_state=proposal_status,
                    governed_intelligence=governed,
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

    def intelligence_opportunity(self, opportunity: Opportunity) -> dict[str, Any]:
        inference = self.session.scalar(select(LLMOpportunityDetail).where(
            LLMOpportunityDetail.opportunity_id == opportunity.id
        ))
        if not inference:
            return {}
        run = self.session.get(LLMRun, inference.llm_run_id)
        reviews = list(self.session.scalars(select(OpportunityReview).where(
            OpportunityReview.opportunity_id == opportunity.id
        ).order_by(OpportunityReview.reviewed_at)))
        evidence = list(self.session.scalars(select(EvidencePackage).join(
            OpportunityEvidence, OpportunityEvidence.evidence_package_id == EvidencePackage.id
        ).join(OpportunityEvaluation, OpportunityEvaluation.id == OpportunityEvidence.opportunity_evaluation_id)
            .where(OpportunityEvaluation.opportunity_id == opportunity.id).distinct()))
        recommendation_ids = list(self.session.scalars(select(RecommendationOpportunity.recommendation_id)
            .where(RecommendationOpportunity.opportunity_id == opportunity.id)))
        recommendations = [self._intelligence_recommendation(row) for row in self.session.scalars(
            select(Recommendation).where(Recommendation.id.in_(recommendation_ids))
        )] if recommendation_ids else []
        evidence_cards = []
        for package in evidence:
            items = list(self.session.scalars(select(EvidencePackageItem).where(
                EvidencePackageItem.evidence_package_id == package.id)))
            rendered_items = []
            for item in items:
                rendered = row_data(item)
                if item.evidence_type == "DEMAND_OBSERVATION" and item.evidence_reference_id:
                    observation = self.session.get(DemandObservation, item.evidence_reference_id)
                    if observation:
                        rendered["authoritative_record"] = {
                            "subject": observation.entity_key,
                            "metric": observation.source_metric,
                            "value": observation.value,
                            "unit": observation.unit,
                            "source": observation.source_system,
                            "observed_date": observation.observed_date,
                            "coverage_state": observation.coverage_state.value,
                        }
                rendered_items.append(rendered)
            evidence_cards.append({**row_data(package), "items": rendered_items})
        latest = reviews[-1] if reviews else None
        evidence_context: dict[str, Any] | None = None
        if opportunity.analytical_entity_id:
            try:
                evidence_context = EvidencePacketService(self.session).build_for_entity(
                    opportunity.tenant_id, opportunity.site_id, opportunity.analytical_entity_id
                ).model_dump(mode="json")
            except IntelligenceValidationError:
                evidence_context = None
        return {
            "governed_intelligence": True,
            "authoritative_evidence": evidence_cards,
            "evidence_context": evidence_context,
            "model_inference": row_data(inference),
            "human_decision": row_data(latest) if latest else None,
            "decision_history": [row_data(item) for item in reviews],
            "recommendations": recommendations,
            "actions": {
                "can_review": True,
                "can_generate_recommendation": bool(latest and latest.decision == "ACCEPTED" and not recommendations),
                "generation_provider": "replay",
                "paid_provider_calls": 0,
            },
            "llm_run": row_data(run, exclude={"response_snapshot_json", "request_fingerprint"}) if run else None,
        }

    def _intelligence_recommendation(self, recommendation: Recommendation) -> dict[str, Any]:
        detail = self.session.scalar(select(LLMRecommendationDetail).where(
            LLMRecommendationDetail.recommendation_id == recommendation.id
        ))
        if not detail:
            return row_data(recommendation)
        reviews = list(self.session.scalars(select(RecommendationReview).where(
            RecommendationReview.recommendation_id == recommendation.id
        ).order_by(RecommendationReview.reviewed_at)))
        proposals = list(self.session.scalars(select(ExperimentProposal).where(
            ExperimentProposal.recommendation_id == recommendation.id
        ).order_by(ExperimentProposal.created_at.desc())))
        opportunities = list(self.session.scalars(select(RecommendationOpportunity.opportunity_id)
            .where(RecommendationOpportunity.recommendation_id == recommendation.id)))
        evidence = list(self.session.scalars(select(RecommendationEvidence.evidence_package_id)
            .where(RecommendationEvidence.recommendation_id == recommendation.id)))
        opportunity_rows = [self.session.get(Opportunity, item) for item in opportunities]
        evidence_rows = [self.session.get(EvidencePackage, item) for item in evidence]
        run = self.session.get(LLMRun, detail.llm_run_id)
        return {**row_data(recommendation), "governed_intelligence": True,
            "model_recommendation": row_data(detail),
            "human_decisions": [row_data(item) for item in reviews],
            "opportunity_ids": opportunities, "evidence_ids": evidence,
            "supporting_opportunities": [{"id": item.id, "title": item.title}
                                         for item in opportunity_rows if item],
            "supporting_evidence": [{"id": item.id, "condition_key": item.condition_key,
                                     "classification": item.classification,
                                     "sufficiency": item.sufficiency.value,
                                     "period_start": item.period_start,
                                     "period_end": item.period_end}
                                    for item in evidence_rows if item],
            "experiment_proposals": [row_data(item) for item in proposals],
            "actions": {"can_select": recommendation.status.value == "READY_FOR_REVIEW",
                        "can_generate_proposal": recommendation.status.value == "ACCEPTED" and not proposals,
                        "generation_provider": "replay", "paid_provider_calls": 0},
            "llm_run": row_data(run, exclude={"response_snapshot_json", "request_fingerprint"}) if run else None}

    def intelligence_recommendations(self, tenant_id: uuid.UUID, site_id: uuid.UUID,
                                     page: int, limit: int) -> dict[str, Any]:
        self.site(tenant_id, site_id)
        query = select(Recommendation).join(LLMRecommendationDetail).where(
            Recommendation.tenant_id == tenant_id, Recommendation.site_id == site_id)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = list(self.session.scalars(query.order_by(Recommendation.created_at.desc())
                                         .offset((page - 1) * limit).limit(limit)))
        return {"items": [self._intelligence_recommendation(row) for row in rows],
                "page": page, "limit": limit, "total": total}

    def intelligence_recommendation(self, recommendation: Recommendation) -> dict[str, Any]:
        return self._intelligence_recommendation(recommendation)

    def experiment_proposals(self, tenant_id: uuid.UUID, site_id: uuid.UUID,
                             page: int, limit: int) -> dict[str, Any]:
        return self.simple_page(ExperimentProposal, tenant_id, site_id, page, limit)

    def experiment_proposal(self, proposal: ExperimentProposal) -> dict[str, Any]:
        reviews = list(self.session.scalars(select(ExperimentProposalReview).where(
            ExperimentProposalReview.experiment_proposal_id == proposal.id)
            .order_by(ExperimentProposalReview.reviewed_at)))
        evidence = list(self.session.scalars(select(ExperimentProposalEvidence.evidence_package_id)
            .where(ExperimentProposalEvidence.experiment_proposal_id == proposal.id)))
        recommendation = self.session.get(Recommendation, proposal.recommendation_id)
        linked = self._intelligence_recommendation(recommendation) if recommendation else None
        return {**row_data(proposal), "human_decisions": [row_data(item) for item in reviews],
                "evidence_ids": evidence, "recommendation": linked,
                "actions": {"can_review": proposal.status in {"READY_FOR_REVIEW", "NEEDS_REVIEW"}},
                "lineage": {"evidence_ids": evidence,
                            "opportunity_ids": linked.get("opportunity_ids", []) if linked else [],
                            "recommendation_id": proposal.recommendation_id,
                            "experiment_proposal_id": proposal.id}}

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
        latest_demand_date = self.session.scalar(
            select(func.max(DemandObservation.observed_date)).where(
                DemandObservation.tenant_id == tenant_id,
                DemandObservation.site_id == site_id,
                DemandObservation.effective_end.is_(None),
            )
        )
        current_provider_volume = (
            self.session.scalar(
                select(func.sum(DemandObservation.value)).where(
                    DemandObservation.tenant_id == tenant_id,
                    DemandObservation.site_id == site_id,
                    DemandObservation.observed_date == latest_demand_date,
                    DemandObservation.effective_end.is_(None),
                )
            )
            if external_allowed and latest_demand_date
            else None
        )
        evidence_package_count = count(EvidencePackage)

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
                "provider_specific_volume": encoded(current_provider_volume),
            },
            "evidence": {
                "packages": evidence_package_count,
                "gaps": self.session.scalar(
                    select(func.count())
                    .select_from(EvidenceGap)
                    .join(EvidencePackage)
                    .where(
                        EvidencePackage.tenant_id == tenant_id, EvidencePackage.site_id == site_id
                    )
                )
                or 0,
                "status": "NOT_PRODUCED" if evidence_package_count == 0 else "AVAILABLE",
                "explanation": external_blocker
                or (
                    f"{evidence_package_count} governed evidence packages were produced from stored demand signals."
                    if evidence_package_count
                    else "No qualifying demand signals have been produced."
                ),
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
        lab_count = (
            self.session.scalar(
                select(func.count())
                .select_from(ExperienceObservation)
                .where(
                    ExperienceObservation.tenant_id == tenant_id,
                    ExperienceObservation.site_id == site_id,
                    ExperienceObservation.measurement_type == ExperienceMeasurementType.LAB,
                )
            )
            or 0
        )
        field_count = (
            self.session.scalar(
                select(func.count())
                .select_from(ExperienceObservation)
                .where(
                    ExperienceObservation.tenant_id == tenant_id,
                    ExperienceObservation.site_id == site_id,
                    ExperienceObservation.measurement_type == ExperienceMeasurementType.FIELD,
                )
            )
            or 0
        )
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
        active_reasons = {
            "gsc": "Active zero-cost authenticated Google collection schedule; read-only property access validated.",
            "ga4": "Active zero-cost authenticated Google collection schedule; read-only property access validated.",
            "experience": f"Active validated zero-cost PageSpeed schedule; {lab_count} LAB observations are stored; CrUX FIELD data is {'available' if field_count else 'currently unavailable (not an error)'}.",
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
        now = datetime.now(timezone.utc)
        liveness = {
            role.value: bool(
                self.session.scalar(
                    select(func.count())
                    .select_from(ExecutorHeartbeat)
                    .where(
                        ExecutorHeartbeat.role == role, ExecutorHeartbeat.lease_expires_at >= now
                    )
                )
            )
            for role in ExecutorRole
        }

        def latest_success(
            schedule: ScheduleDefinition,
            freshness: FreshnessState | None,
            pipeline: PipelineDefinition,
        ) -> Any:
            if freshness and freshness.last_successful_at:
                return encoded(freshness.last_successful_at)
            if schedule.data_source_connection_id:
                connection = self.session.get(
                    DataSourceConnection, schedule.data_source_connection_id
                )
                if connection and connection.last_successful_sync_at:
                    return encoded(connection.last_successful_sync_at)
            completed_at = self.session.scalar(
                select(func.max(OrchestrationRun.completed_at)).where(
                    OrchestrationRun.tenant_id == tenant_id,
                    OrchestrationRun.site_id == site_id,
                    OrchestrationRun.pipeline_id == pipeline.id,
                    OrchestrationRun.status == "SUCCEEDED",
                )
            )
            return encoded(completed_at)

        return {
            "items": [
                self._pipeline_capability(
                    row,
                    fresh,
                    pipeline,
                    latest_success(row, fresh, pipeline),
                    liveness,
                    disabled_reasons,
                    active_reasons,
                )
                for row, fresh, pipeline in schedules
            ],
            "executor_liveness": liveness,
            "fixture_ai_provider": True,
            "production_ai_operational": False,
            "experience": {
                "lab_observations": lab_count,
                "field_observations": field_count,
                "crux_state": "DATA_AVAILABLE" if field_count else "NO_FIELD_DATA_AVAILABLE",
                "semantics": "Lighthouse LAB observations are never represented as CrUX FIELD data.",
            },
        }

    def _pipeline_capability(
        self,
        row: ScheduleDefinition,
        fresh: FreshnessState | None,
        pipeline: PipelineDefinition,
        latest_success: Any,
        liveness: dict[str, bool],
        disabled_reasons: dict[str, str],
        active_reasons: dict[str, str],
    ) -> dict[str, Any]:
        obligations = self.session.scalars(
            select(OrchestrationObligation)
            .where(OrchestrationObligation.schedule_id == row.id)
            .order_by(OrchestrationObligation.due_at.desc())
        ).all()
        pending = [
            item
            for item in obligations
            if item.status not in {ObligationStatus.SATISFIED, ObligationStatus.EXPIRED}
        ]
        overdue = [item for item in pending if item.due_at < datetime.now(timezone.utc)]
        latest = obligations[0] if obligations else None
        timeliness = (
            "NOT_YET_DUE"
            if not latest
            and row.next_scheduled_at
            and row.next_scheduled_at > datetime.now(timezone.utc)
            else "ON_TIME"
            if latest and latest.satisfied_at and latest.satisfied_at <= latest.due_at
            else "RECOVERED_LATE"
            if latest and latest.status is ObligationStatus.SATISFIED
            else "MISSED_UNSATISFIED"
            if latest and latest.due_at < datetime.now(timezone.utc)
            else "DISABLED"
            if row.status.value == "DISABLED"
            else "NOT_YET_DUE"
        )
        run_count = (
            self.session.scalar(
                select(func.count())
                .select_from(OrchestrationRun)
                .where(OrchestrationRun.schedule_id == row.id)
            )
            or 0
        )
        provider_reporting_date: Any = None
        if pipeline.key == "gsc":
            provider_reporting_date = self.session.scalar(
                select(func.max(GSCSearchObservation.observed_date)).where(
                    GSCSearchObservation.tenant_id == row.tenant_id,
                    GSCSearchObservation.site_id == row.site_id,
                    GSCSearchObservation.effective_end.is_(None),
                )
            )
        elif pipeline.key == "ga4":
            provider_reporting_date = self.session.scalar(
                select(func.max(GA4EventObservation.observed_date)).where(
                    GA4EventObservation.tenant_id == row.tenant_id,
                    GA4EventObservation.site_id == row.site_id,
                    GA4EventObservation.effective_end.is_(None),
                )
            )
        automation_state = (
            "DISABLED"
            if row.status.value == "DISABLED"
            else "EXECUTOR_OFFLINE"
            if not liveness.get("SCHEDULER") or not liveness.get("WORKER")
            else "PROVIDER_DATA_PENDING"
            if latest and latest.status is ObligationStatus.PROVIDER_DATA_PENDING
            else "RECOVERING"
            if overdue
            else "AWAITING_FIRST_SCHEDULED_RUN"
            if not obligations
            and row.next_scheduled_at
            and row.next_scheduled_at > datetime.now(timezone.utc)
            else "HEALTHY"
        )
        return {
            "schedule": row.name,
            "status": row.status.value,
            "latest_success": latest_success,
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
                and pipeline.handler_key in {"DBT", "LOCAL_PROCESSING", "COMPETITIVE_EVENTS"}
                else active_reasons.get(pipeline.key)
                if row.status.value == "ENABLED"
                else None
            ),
            "pipeline_key": pipeline.key,
            "paid_provider": pipeline.paid_provider,
            "source_health": {
                "state": (
                    "STALE"
                    if fresh and fresh.stale_since
                    else "CURRENT"
                    if latest_success
                    else "NO_SOURCE_HISTORY"
                ),
                "latest_ingestion_success": latest_success,
                "latest_provider_reporting_date": encoded(provider_reporting_date),
                "provider_lag_days": (
                    (datetime.now(timezone.utc).date() - provider_reporting_date).days
                    if provider_reporting_date
                    else None
                ),
                "freshness_sla_seconds": row.freshness_sla_seconds,
                "stale_since": encoded(fresh.stale_since) if fresh else None,
            },
            "automation_health": {
                "state": automation_state,
                "next_due_at": encoded(row.next_scheduled_at),
                "last_obligation_status": encoded(latest.status) if latest else None,
                "last_obligation_due_at": encoded(latest.due_at) if latest else None,
                "last_completion_outcome": encoded(latest.completion_outcome) if latest else None,
                "timeliness": timeliness,
                "pending_obligations": len(pending),
                "overdue_obligations": len(overdue),
                "orchestration_run_count": run_count,
                "scheduler_alive": liveness.get("SCHEDULER", False),
                "worker_alive": liveness.get("WORKER", False),
                "retry_profile": row.retry_profile,
            },
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
