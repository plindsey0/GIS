from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.collection_planning.service import CollectionPlanningService, normalize_target
from gis.intelligence.service import EvidencePacketService, IntelligenceValidationError
from gis.models import (
    CollectionCadence,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionPriorityTier,
    CollectionRequirement,
    CollectionRequirementCapability,
    CollectionRequirementStatus,
    CollectionTargetType,
    CollectorCapability,
    DataSource,
    EventSemanticClass,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceReassessmentStatus,
    ExperimentProposal,
    ExperimentProposalReview,
    MarketDefinition,
    Opportunity,
    PipelineDefinition,
    ProposalArtifactType,
    Recommendation,
    RecommendationReview,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


CAPABILITY_BY_GAP = {
    "TARGET_PAGE_CONTENT_OBSERVATION": CollectionRequirementCapability.OWNED_PAGE_CONTENT,
    "EXACT_QUERY_SERP_COMPETITOR_EVIDENCE": CollectionRequirementCapability.EXACT_QUERY_SERP,
}

COLLECTOR_BY_CAPABILITY = {
    CollectionRequirementCapability.OWNED_PAGE_CONTENT: "CONTENT_URL",
    CollectionRequirementCapability.EXACT_QUERY_SERP: "SERP",
}

REQUESTED_CHARACTERISTICS = {
    CollectionRequirementCapability.OWNED_PAGE_CONTENT: [
        "timestamp", "http_status", "canonical_url", "robots_indexability", "html_content",
        "title", "headings", "explanatory_content", "structured_data",
    ],
    CollectionRequirementCapability.EXACT_QUERY_SERP: [
        "timestamp", "ranked_results", "result_urls", "result_domains", "result_types",
        "serp_features", "owned_candidate_presence", "observed_competitors",
        "provider_provenance", "market_parameters",
    ],
}

UNSUPPORTED_CHARACTERISTICS = {
    CollectionRequirementCapability.OWNED_PAGE_CONTENT: [
        "browser-rendered_interaction_state", "accessibility_conformance_audit",
        "calculator_formula_correctness",
    ],
    CollectionRequirementCapability.EXACT_QUERY_SERP: [],
}


class InvestigationHandoffService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def derive_requirements(self, proposal_id: uuid.UUID) -> list[CollectionRequirement]:
        proposal = self.session.get(ExperimentProposal, proposal_id)
        if not proposal or proposal.proposal_type is not ProposalArtifactType.INVESTIGATION:
            raise IntelligenceValidationError("Collection requirements require an investigation proposal.")
        if proposal.status != "APPROVED":
            raise IntelligenceValidationError("Collection requirements require human approval.")
        recommendation = self.session.get(Recommendation, proposal.recommendation_id)
        if not recommendation or recommendation.tenant_id != proposal.tenant_id:
            raise IntelligenceValidationError("Investigation recommendation lineage is invalid.")
        opportunity = self.session.get(Opportunity, recommendation.opportunity_id)
        if not opportunity or opportunity.site_id != proposal.site_id:
            raise IntelligenceValidationError("Investigation opportunity lineage is invalid.")
        packet = EvidencePacketService(self.session).build_for_entity(
            proposal.tenant_id, proposal.site_id, opportunity.analytical_entity_id
        )
        reviews = list(self.session.scalars(select(ExperimentProposalReview).where(
            ExperimentProposalReview.experiment_proposal_id == proposal.id
        ).order_by(ExperimentProposalReview.reviewed_at)))
        recommendation_reviews = list(self.session.scalars(select(RecommendationReview).where(
            RecommendationReview.recommendation_id == recommendation.id
        ).order_by(RecommendationReview.reviewed_at)))
        human_constraints = [item.comment for item in recommendation_reviews if item.comment]
        human_constraints.extend(item.comment for item in reviews if item.comment)
        owned_url = str(packet.owned_surfaces[0]["url"]) if packet.owned_surfaces else ""
        query = str(packet.entity_context.get("canonical_key", ""))
        created: list[CollectionRequirement] = []
        for gap in packet.evidence_gaps:
            gap_type = str(gap.get("gap_type", "UNSPECIFIED_EVIDENCE_NEED"))
            gap_id = uuid.UUID(str(gap["gap_id"]))
            capability = CAPABILITY_BY_GAP.get(
                gap_type, CollectionRequirementCapability.UNSUPPORTED
            )
            if capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT:
                target_type, target = CollectionTargetType.URL, owned_url
            else:
                target_type, target = CollectionTargetType.QUERY, query
            if not target:
                capability = CollectionRequirementCapability.UNSUPPORTED
                target = query or proposal.target_url_or_resource
            normalized, _ = normalize_target(target_type, target)
            identity_hash = _digest([
                proposal.id, gap_id, capability.value, target_type.value, normalized,
                packet.entity_context.get("country_code"),
                packet.entity_context.get("language_code"), packet.entity_context.get("device"),
            ])
            existing = self.session.scalar(select(CollectionRequirement).where(
                CollectionRequirement.identity_hash == identity_hash
            ))
            if existing:
                created.append(existing)
                continue
            persisted_gap = self.session.get(EvidenceGap, gap_id)
            supported = capability is not CollectionRequirementCapability.UNSUPPORTED
            row = CollectionRequirement(
                tenant_id=proposal.tenant_id,
                site_id=proposal.site_id,
                proposal_id=proposal.id,
                recommendation_id=recommendation.id,
                opportunity_id=opportunity.id,
                analytical_entity_id=opportunity.analytical_entity_id,
                evidence_gap_id=persisted_gap.id if persisted_gap else None,
                gap_reference_id=gap_id,
                gap_type=gap_type,
                capability=capability,
                target_type=target_type,
                target_value=target,
                normalized_target=normalized,
                country_code=str(packet.entity_context.get("country_code") or "") or None,
                language_code=str(packet.entity_context.get("language_code") or "") or None,
                device=str(packet.entity_context.get("device") or "") or None,
                requested_characteristics_json=REQUESTED_CHARACTERISTICS.get(capability, []),
                unsupported_characteristics_json=(
                    UNSUPPORTED_CHARACTERISTICS.get(capability, []) if supported
                    else [str(gap.get("requested_capability") or gap.get("description") or gap_type)]
                ),
                rationale=str(gap.get("description") or proposal.objective),
                rights_constraints_json=[
                    "tenant/site/entity scope required", "governed retention rights required",
                    "provider and cost approval remain separate",
                ],
                human_constraints_json=human_constraints,
                priority=CollectionPriorityTier.HIGH if supported else CollectionPriorityTier.MEDIUM,
                freshness_expectation=CollectionCadence.ON_DEMAND,
                status=(CollectionRequirementStatus.REQUESTED if supported
                        else CollectionRequirementStatus.UNSUPPORTED),
                blocker=None if supported else "No governed collector mapping for this evidence need",
                cost_class="UNKNOWN",
                reassessment_status=EvidenceReassessmentStatus.NOT_REASSESSED,
                identity_hash=identity_hash,
            )
            self.session.add(row)
            self.session.flush()
            created.append(row)
        return created

    def promote_to_candidate_plan(
        self, requirement_id: uuid.UUID, actor: str
    ) -> CollectionRequirement:
        requirement = self.session.get(CollectionRequirement, requirement_id)
        if not requirement or not actor.strip():
            raise IntelligenceValidationError("A scoped requirement and human actor are required.")
        if requirement.status is CollectionRequirementStatus.UNSUPPORTED:
            raise IntelligenceValidationError("Unsupported requirements cannot be promoted.")
        recommendation = self.session.get(Recommendation, requirement.recommendation_id)
        market = self.session.get(
            MarketDefinition, recommendation.market_definition_id if recommendation else None
        )
        if not market or market.tenant_id != requirement.tenant_id or market.site_id != requirement.site_id:
            raise IntelligenceValidationError("Requirement has no governed market for collection planning.")
        planner = CollectionPlanningService(self.session)
        target = planner.register_target(
            market,
            requirement.target_type,
            requirement.target_value,
            source_system="GIS_INTELLIGENCE",
            evidence_type="APPROVED_INVESTIGATION_REQUIREMENT",
            evidence_identifier=str(requirement.id),
            evidence_at=_now(),
            semantic_class=EventSemanticClass.GIS_DERIVED,
            signal_name="approved_evidence_requirement",
            signal_value=Decimal(1),
            human_managed=True,
            metadata={
                "proposal_id": str(requirement.proposal_id),
                "requirement_id": str(requirement.id), "actor": actor,
                "capability": requirement.capability.value,
            },
        )
        requirement.collection_target_id = target.id
        requirement.status = CollectionRequirementStatus.CANDIDATE
        run = planner.plan(market)
        collector_key = COLLECTOR_BY_CAPABILITY[requirement.capability]
        plan_item = self.session.scalar(select(CollectionPlanItem).join(
            CollectorCapability,
            CollectorCapability.id == CollectionPlanItem.collector_capability_id,
        ).where(
            CollectionPlanItem.decision_id.in_(select(CollectionPlanningDecision.id).where(
                CollectionPlanningDecision.planning_run_id == run.id,
                CollectionPlanningDecision.target_id == target.id,
            )),
            CollectorCapability.capability_key == collector_key,
        ))
        if plan_item:
            requirement.collection_plan_item_id = plan_item.id
            capability = self.session.get(CollectorCapability, plan_item.collector_capability_id)
            pipeline = (
                self.session.get(PipelineDefinition, capability.pipeline_id)
                if capability else None
            )
            source = (
                self.session.get(DataSource, pipeline.data_source_id)
                if pipeline and pipeline.data_source_id else None
            )
            requirement.provider_key = (
                source.key if source else pipeline.handler_key if pipeline else None
            )
            if pipeline and pipeline.paid_provider:
                requirement.cost_class = "KNOWN_PAID"
            elif plan_item.estimated_cost_per_run is None:
                requirement.cost_class = "UNKNOWN"
            elif plan_item.estimated_cost_per_run > 0:
                requirement.cost_class = "KNOWN_PAID"
            else:
                requirement.cost_class = "FREE_LOCAL"
            requirement.blocker = (
                None if plan_item.blocker.value == "NONE" else plan_item.blocker.value
            )
        else:
            requirement.status = CollectionRequirementStatus.BLOCKED
            requirement.blocker = f"No {collector_key} collection plan item is available"
        return requirement

    def reassess(
        self,
        requirement_id: uuid.UUID,
        evidence_package_id: uuid.UUID | None,
        *,
        collection_failed: bool = False,
    ) -> CollectionRequirement:
        requirement = self.session.get(CollectionRequirement, requirement_id)
        if not requirement:
            raise IntelligenceValidationError("Collection requirement not found.")
        requirement.reassessed_at = _now()
        if collection_failed:
            requirement.status = CollectionRequirementStatus.FAILED
            requirement.reassessment_status = EvidenceReassessmentStatus.FAILED
            requirement.reassessment_notes = "Collection failed; the evidence gap remains open."
            return requirement
        package = self.session.get(EvidencePackage, evidence_package_id) if evidence_package_id else None
        if not package:
            requirement.reassessment_status = EvidenceReassessmentStatus.STILL_INSUFFICIENT
            requirement.reassessment_notes = "No governed evidence package was supplied for reassessment."
            return requirement
        if (
            package.tenant_id != requirement.tenant_id
            or package.site_id != requirement.site_id
            or package.analytical_entity_id != requirement.analytical_entity_id
        ):
            raise IntelligenceValidationError("Evidence package is outside requirement scope.")
        items = list(self.session.scalars(select(EvidencePackageItem).where(
            EvidencePackageItem.evidence_package_id == package.id
        )))
        expected_tokens = (
            {"CONTENT", "PAGE"}
            if requirement.capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT
            else {"SERP"}
        )

        def target_matches(item: EvidencePackageItem) -> bool:
            metadata = item.metadata_json or {}
            if requirement.capability is CollectionRequirementCapability.OWNED_PAGE_CONTENT:
                observed = str(metadata.get("url") or metadata.get("canonical_url") or "")
                if not observed:
                    return False
                normalized, _ = normalize_target(CollectionTargetType.URL, observed)
                return normalized == requirement.normalized_target
            observed = str(metadata.get("query") or metadata.get("keyword") or "")
            if not observed:
                return False
            normalized, _ = normalize_target(CollectionTargetType.QUERY, observed)
            return (
                normalized == requirement.normalized_target
                and metadata.get("country_code") == requirement.country_code
                and metadata.get("language_code") == requirement.language_code
                and metadata.get("device") == requirement.device
            )

        matching = any(
            any(token in " ".join(filter(None, [item.evidence_type, item.root_source_key])).upper()
                for token in expected_tokens)
            and target_matches(item)
            and item.rights_usability.value in {"USABLE", "PARTIALLY_USABLE"}
            and item.method_compatibility.value == "COMPATIBLE"
            and item.scope_compatibility.value == "COMPATIBLE"
            for item in items
        )
        if (
            package.sufficiency.value == "SUPPORTED"
            and package.rights_usability.value in {"USABLE", "PARTIALLY_USABLE"}
            and matching
        ):
            requirement.status = CollectionRequirementStatus.SATISFIED
            requirement.reassessment_status = EvidenceReassessmentStatus.SATISFIED
            requirement.satisfying_evidence_package_id = package.id
            requirement.intelligence_reassessment_eligible_at = requirement.reassessed_at
            requirement.reassessment_notes = (
                "Governed package satisfies scope, rights, compatibility, and sufficiency checks."
            )
            if requirement.evidence_gap_id:
                gap = self.session.get(EvidenceGap, requirement.evidence_gap_id)
                if gap and not gap.resolved_at:
                    gap.resolved_at = requirement.reassessed_at
        else:
            requirement.reassessment_status = EvidenceReassessmentStatus.STILL_INSUFFICIENT
            requirement.reassessment_notes = (
                "Collection exists, but governed evidence quality or capability remains insufficient."
            )
        return requirement
