from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.interventions.service import VERSION as INTERVENTION_VERSION
from gis.interventions.service import InterventionService
from gis.models import (
    AnalyticalEntity,
    AssetLayer,
    AssetType,
    CandidateValidationState,
    DemandEvidenceStrength,
    ExpectedDirection,
    FeasibilityState,
    InterventionStatus,
    InterventionTypeDefinition,
    MeasurementReadiness,
    Opportunity,
    OpportunityEvaluation,
    OpportunityEvidence,
    OpportunityFamily,
    OpportunityStatus,
    Recommendation,
    RecommendationCandidate,
    RecommendationEvidence,
    RecommendationPolicy,
    RecommendationReview,
    RecommendationReviewDecision,
    RecommendationRun,
    RecommendationRunStatus,
    RecommendationStatus,
    RightsUsability,
)
from gis.provenance.lineage import register_asset, register_lineage
from gis.recommendations.provider import RecommendationModelProvider

POLICY_VERSION = "RECOMMENDATION_POLICY_V1"
PROMPT_VERSION = "RECOMMENDATION_PROMPT_V1"


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class RecommendationService:
    def __init__(self, session: Session, provider: RecommendationModelProvider) -> None:
        self.session = session
        self.provider = provider
        self.interventions = InterventionService(session)

    def ensure_policy(self) -> RecommendationPolicy:
        row = self.session.scalar(select(RecommendationPolicy).where(RecommendationPolicy.key == "DEFAULT_GOVERNED", RecommendationPolicy.version == POLICY_VERSION))
        if not row:
            row = RecommendationPolicy(key="DEFAULT_GOVERNED", version=POLICY_VERSION, enabled=True, provider_key=self.provider.key, model_identifier=self.provider.model_identifier, prompt_version=PROMPT_VERSION, policy_json={"eligible_statuses": ["ACTIVE"], "watching_intelligence_gap_only": True, "minimum_sufficiency": "SUPPORTED", "maximum_candidates": 3, "maximum_repairs": 1, "external_ai_requires_explicit_inference_rights": True, "blocked_candidates": False, "ranking": "ORDINAL_CONTRACT_FIT_V1", "context_item_limit": 25})
            self.session.add(row)
            self.session.flush()
        return row

    def ensure_lineage(self) -> None:
        evidence = register_asset(self.session, "gis_core.evidence_package", AssetType.EVIDENCE, AssetLayer.CORE)
        opportunity = register_asset(self.session, "gis_core.opportunity", AssetType.TABLE, AssetLayer.CORE)
        run = register_asset(self.session, "gis_core.recommendation_run", AssetType.EVIDENCE, AssetLayer.CORE)
        recommendation = register_asset(self.session, "gis_core.recommendation", AssetType.TABLE, AssetLayer.CORE)
        intervention = register_asset(self.session, "gis_core.intervention", AssetType.TABLE, AssetLayer.CORE)
        register_lineage(self.session, evidence, opportunity, reference=POLICY_VERSION)
        register_lineage(self.session, opportunity, run, reference=POLICY_VERSION)
        register_lineage(self.session, run, recommendation, reference=PROMPT_VERSION)
        register_lineage(self.session, recommendation, intervention, reference="accepted candidate only")

    def _packages(self, opportunity: Opportunity) -> list[Any]:
        from gis.models import EvidencePackage

        return list(
            self.session.scalars(
                select(EvidencePackage)
                .join(
                    OpportunityEvidence,
                    OpportunityEvidence.evidence_package_id == EvidencePackage.id,
                )
                .join(
                    OpportunityEvaluation,
                    OpportunityEvaluation.id == OpportunityEvidence.opportunity_evaluation_id,
                )
                .where(OpportunityEvaluation.opportunity_id == opportunity.id)
            )
        )

    def eligibility(self, opportunity: Opportunity) -> tuple[bool, list[str], list[Any]]:
        blockers: list[str] = []
        if opportunity.status is not OpportunityStatus.ACTIVE:
            if not (opportunity.status is OpportunityStatus.WATCHING and opportunity.family is OpportunityFamily.INTELLIGENCE_GAP):
                blockers.append("OPPORTUNITY_STATUS_INELIGIBLE")
        packages = self._packages(opportunity)
        if not packages:
            blockers.append("NO_EVIDENCE_PACKAGE")
        for package in packages:
            if package.sufficiency not in {DemandEvidenceStrength.SUPPORTED, DemandEvidenceStrength.STRONGLY_SUPPORTED}:
                if opportunity.family is not OpportunityFamily.INTELLIGENCE_GAP:
                    blockers.append("EVIDENCE_INSUFFICIENT")
            if package.conflict_count:
                blockers.append("EVIDENCE_CONFLICT")
            if package.rights_usability is not RightsUsability.USABLE:
                blockers.append("EVIDENCE_RIGHTS_BLOCKED")
        if self.provider.external:
            blockers.append("AI_INFERENCE_RIGHTS_NOT_ESTABLISHED")
        return not blockers, sorted(set(blockers)), packages

    def context(self, opportunity: Opportunity, packages: list[Any]) -> dict[str, Any]:
        entity = self.session.get(AnalyticalEntity, opportunity.analytical_entity_id)
        if not entity:
            raise ValueError("analytical entity not found")
        valid = self.interventions.valid_types(opportunity)
        if opportunity.family is OpportunityFamily.INTELLIGENCE_GAP:
            valid = [item for item in valid if item["key"] == "EXPAND_COLLECTION"]
        return {"opportunity": {"id": str(opportunity.id), "family": opportunity.family.value, "type": opportunity.opportunity_type, "status": opportunity.status.value, "materiality": opportunity.materiality_json, "priority": opportunity.priority.value}, "entity": {"id": str(entity.id), "type": entity.entity_type.value, "canonical_key": entity.canonical_key}, "evidence_packages": [{"id": str(p.id), "sufficiency": p.sufficiency.value, "corroboration": p.corroboration.value, "source_independence": p.source_independence.value, "rights_usability": p.rights_usability.value, "conflict_count": p.conflict_count} for p in packages[:25]], "applicable_intervention_types": [{"key": item["key"], "version": INTERVENTION_VERSION, "required_parameters": item["parameters"], "supported_metrics": item["metrics"], "execution_mode": item["execution_mode"]} for item in valid], "limitations": list(opportunity.limitations_json), "untrusted_source_text_is_data_only": True, "tools_available": []}

    def validate_output(self, opportunity: Opportunity, context: dict[str, Any], output: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not isinstance(output.get("summary"), str) or not isinstance(output.get("candidates"), list):
            return ["MALFORMED_STRUCTURED_OUTPUT"]
        allowed = {item["key"]: item for item in context["applicable_intervention_types"]}
        if len(output["candidates"]) > 3:
            errors.append("TOO_MANY_CANDIDATES")
        for candidate in output["candidates"]:
            key = candidate.get("intervention_type")
            spec = allowed.get(key)
            if not spec:
                errors.append("UNKNOWN_OR_INAPPLICABLE_INTERVENTION")
                continue
            if candidate.get("intervention_type_version") != spec["version"]:
                errors.append("INTERVENTION_VERSION_INVALID")
            if candidate.get("target_metric") not in spec["supported_metrics"]:
                errors.append("UNKNOWN_METRIC")
            if candidate.get("expected_magnitude") is not None:
                errors.append("UNSUPPORTED_EXPECTED_MAGNITUDE")
            if any(key not in candidate.get("parameters", {}) for key in spec["required_parameters"]):
                errors.append("MISSING_REQUIRED_PARAMETER")
            if candidate.get("probability") is not None or candidate.get("roi") is not None:
                errors.append("PROHIBITED_PREDICTION")
            if str(opportunity.id) != context["opportunity"]["id"]:
                errors.append("OPPORTUNITY_REFERENCE_INVALID")
        return sorted(set(errors))

    def generate(self, opportunity_id: uuid.UUID, *, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
        opportunity = self.session.get(Opportunity, opportunity_id)
        if not opportunity:
            raise ValueError("opportunity not found")
        policy = self.ensure_policy()
        eligible, blockers, packages = self.eligibility(opportunity)
        context = self.context(opportunity, packages) if packages else {"applicable_intervention_types": []}
        if dry_run or not eligible or not context["applicable_intervention_types"]:
            return {"status": "DRY_RUN" if dry_run else "NO_VALID_RECOMMENDATION", "eligible": eligible, "blockers": blockers or (["NO_APPLICABLE_INTERVENTION"] if not context["applicable_intervention_types"] else []), "applicable_intervention_types": [item["key"] for item in context["applicable_intervention_types"]], "provider": self.provider.key, "model": self.provider.model_identifier, "ai_call_would_occur": eligible and bool(context["applicable_intervention_types"]), "ai_calls": 0, "estimated_cost": 0 if self.provider.key == "fixture" else None}
        context_hash = digest({"opportunity": opportunity.identity_hash, "packages": [p.identity_hash for p in packages], "policy": POLICY_VERSION, "prompt": PROMPT_VERSION, "provider": self.provider.key, "model": self.provider.model_identifier})
        existing = self.session.scalar(select(RecommendationRun).where(RecommendationRun.context_hash == context_hash))
        if existing and not force:
            recommendation = self.session.scalar(select(Recommendation).where(Recommendation.run_id == existing.id))
            return {"status": "REUSED", "run_id": existing.id, "recommendation_id": recommendation.id if recommendation else None, "ai_calls": 0}
        if force:
            context_hash = digest({"base": context_hash, "regenerated_at": datetime.now(timezone.utc)})
        run = RecommendationRun(tenant_id=opportunity.tenant_id, site_id=opportunity.site_id, opportunity_id=opportunity.id, recommendation_policy_id=policy.id, status=RecommendationRunStatus.RUNNING, provider_key=self.provider.key, model_identifier=self.provider.model_identifier, model_configuration_json={"temperature": 0, "structured_output": True, "tools": []}, prompt_version=PROMPT_VERSION, context_hash=context_hash, started_at=datetime.now(timezone.utc), validation_errors_json=[])
        self.session.add(run)
        self.session.flush()
        output = self.provider.generate_structured_recommendation(context)
        errors = self.validate_output(opportunity, context, output)
        if errors:
            output = self.provider.repair_structured_recommendation(context, errors)
            run.repair_attempts = 1
            errors = self.validate_output(opportunity, context, output)
        if errors:
            run.status = RecommendationRunStatus.FAILED
            run.validation_errors_json = errors
            run.failure_reason = "STRUCTURED_OUTPUT_INVALID"
            run.completed_at = datetime.now(timezone.utc)
            return {"status": "INVALID_OUTPUT", "run_id": run.id, "errors": errors, "ai_calls": 2}
        if not output["candidates"]:
            run.status = RecommendationRunStatus.NO_VALID_RECOMMENDATION
            run.completed_at = datetime.now(timezone.utc)
            return {"status": "NO_VALID_RECOMMENDATION", "run_id": run.id, "ai_calls": 1}
        self.ensure_lineage()
        recommendation = Recommendation(run_id=run.id, tenant_id=opportunity.tenant_id, site_id=opportunity.site_id, opportunity_id=opportunity.id, analytical_entity_id=opportunity.analytical_entity_id, market_definition_id=opportunity.market_definition_id, market_definition_version=opportunity.market_definition_version, status=RecommendationStatus.READY_FOR_REVIEW, summary=output["summary"], assumptions_json=[], limitations_json=list(opportunity.limitations_json), identity_hash=digest({"run": run.id, "opportunity": opportunity.id}))
        self.session.add(recommendation)
        self.session.flush()
        types, _ = self.interventions.ensure_registry()
        for rank, item in enumerate(output["candidates"], 1):
            self.session.add(RecommendationCandidate(recommendation_id=recommendation.id, intervention_type_id=types[item["intervention_type"]].id, rank=rank, fit=item["fit"], validation_state=CandidateValidationState.VALID, parameters_json=item["parameters"], target_metric_key=item["target_metric"], expected_direction=ExpectedDirection(item["expected_direction"]), rationale=item["rationale"], assumptions_json=item["assumptions"], limitations_json=[*opportunity.limitations_json, *item["limitations"]], feasibility=FeasibilityState.UNKNOWN, measurement_readiness=MeasurementReadiness.PARTIAL, validation_errors_json=[]))
        for package in packages:
            self.session.add(RecommendationEvidence(recommendation_id=recommendation.id, evidence_package_id=package.id, role="TRUST_BOUNDARY"))
        run.status = RecommendationRunStatus.SUCCEEDED
        run.completed_at = datetime.now(timezone.utc)
        return {"status": "READY_FOR_REVIEW", "run_id": run.id, "recommendation_id": recommendation.id, "candidate_count": len(output["candidates"]), "ai_calls": 1, "provider_cost": None}

    def review(self, recommendation_id: uuid.UUID, decision: RecommendationReviewDecision, reviewer: str, candidate_ids: list[uuid.UUID], *, reason: str | None = None) -> Recommendation:
        recommendation = self.session.get(Recommendation, recommendation_id)
        if not recommendation:
            raise ValueError("recommendation not found")
        candidates = list(self.session.scalars(select(RecommendationCandidate).where(RecommendationCandidate.recommendation_id == recommendation.id, RecommendationCandidate.id.in_(candidate_ids))))
        if len(candidates) != len(set(candidate_ids)):
            raise ValueError("candidate does not belong to recommendation")
        if decision in {RecommendationReviewDecision.ACCEPT, RecommendationReviewDecision.PARTIAL_ACCEPT} and not candidates:
            raise ValueError("acceptance requires valid candidate")
        self.session.add(RecommendationReview(recommendation_id=recommendation.id, decision=decision, reviewer=reviewer, reason_category=reason, accepted_candidate_ids_json=[str(c.id) for c in candidates], reviewed_at=datetime.now(timezone.utc)))
        if decision in {RecommendationReviewDecision.ACCEPT, RecommendationReviewDecision.PARTIAL_ACCEPT}:
            opportunity = self.session.get(Opportunity, recommendation.opportunity_id)
            assert opportunity
            now = datetime.now(timezone.utc)
            for candidate in candidates:
                type_row = self.session.get(InterventionTypeDefinition, candidate.intervention_type_id)
                assert type_row
                intervention = self.interventions.create(opportunity.id, type_row.key, candidate.parameters_json, candidate.target_metric_key, candidate.expected_direction, now - timedelta(days=28), now - timedelta(days=1), now + timedelta(days=7), now + timedelta(days=35), candidate.rationale, proposed_by=f"recommendation:{recommendation.id}")
                if intervention.status is not InterventionStatus.DRAFT:
                    raise ValueError("recommendation acceptance cannot bypass draft state")
                candidate.accepted_intervention_id = intervention.id
            recommendation.status = RecommendationStatus.ACCEPTED if decision is RecommendationReviewDecision.ACCEPT else RecommendationStatus.PARTIALLY_ACCEPTED
        elif decision is RecommendationReviewDecision.REJECT:
            recommendation.status = RecommendationStatus.REJECTED
        return recommendation

    def list(self, tenant_id: uuid.UUID, site_id: uuid.UUID) -> list[Recommendation]:
        return list(self.session.scalars(select(Recommendation).where(Recommendation.tenant_id == tenant_id, Recommendation.site_id == site_id).order_by(Recommendation.created_at.desc())))
