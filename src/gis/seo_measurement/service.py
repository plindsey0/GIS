from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.content_briefs.service import ContentBriefService
from gis.evidence_quality.analysis import normalize_query, normalize_url
from gis.models import (
    ContentBrief,
    DataRightsPolicy,
    DataSourceConnection,
    GSCSearchObservation,
    MarketDefinition,
    PageChangeProposal,
    QualityFlag,
    RightsDecision,
    SEOImplementationRecord,
    SEOInvestigation,
    SEOMeasurementPlan,
    SEOMeasurementReview,
    SEOOutcomeAssessment,
)

METHOD = "GSC_QUERY_PAGE_PRE_POST"
VERSION = "seo_measurement_v1"
IMPLEMENTATION_STATES = {"NOT_STARTED", "PARTIALLY_IMPLEMENTED", "IMPLEMENTED",
                         "ROLLED_BACK", "UNKNOWN", "VERIFICATION_REQUIRED"}
REVIEW_DECISIONS = {"CONFIRM", "DISAGREE", "NEEDS_MORE_DATA", "ACCEPT_INCONCLUSIVE",
                    "APPROVE_FOLLOW_UP", "CLOSE_INVESTIGATION"}


class SEOMeasurementError(ValueError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SEOMeasurementService:
    """Deterministic observational measurement; never collects, deploys, or experiments."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def eligibility(self, proposal_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> dict[str, Any]:
        proposal = self.session.get(PageChangeProposal, proposal_id)
        failures: list[dict[str, str]] = []
        if not proposal:
            failures.append({"gate": "PROPOSAL", "reason": "Proposal does not exist."})
            return {"eligible": False, "failed_gates": failures}
        brief = self.session.get(ContentBrief, proposal.content_brief_id)
        investigation = self.session.get(SEOInvestigation, proposal.investigation_id)
        if not brief or brief.tenant_id != tenant_id or brief.site_id != site_id:
            failures.append({"gate": "SCOPE", "reason": "Brief is outside tenant/site scope."})
        if not investigation or investigation.tenant_id != tenant_id or investigation.site_id != site_id:
            failures.append({"gate": "SCOPE", "reason": "Investigation is outside tenant/site scope."})
        if proposal.status not in {"APPROVED", "READY_FOR_MEASUREMENT_PLANNING"}:
            failures.append({"gate": "APPROVAL", "reason": "Proposal is not currently approved."})
        if brief and investigation and (brief.investigation_id != investigation.id
                or brief.query_entity_id != investigation.query_entity_id
                or brief.page_entity_id != investigation.candidate_page_entity_id
                or brief.market_definition_id != investigation.market_definition_id
                or normalize_query(brief.exact_query) != normalize_query(investigation.exact_query)
                or normalize_url(brief.candidate_url) != normalize_url(investigation.normalized_candidate_url)):
            failures.append({"gate": "EXACT_SCOPE", "reason": "Proposal lineage has incompatible query, page, or market scope."})
        current_fingerprint = None
        if brief and investigation:
            current_fingerprint = ContentBriefService(self.session).context(investigation)["fingerprint"]
        if brief and (proposal.evidence_fingerprint != brief.input_fingerprint
                or proposal.evidence_fingerprint != current_fingerprint):
            failures.append({"gate": "STALE_EVIDENCE", "reason": "Proposal evidence fingerprint is stale."})
        return {"eligible": not failures, "failed_gates": failures,
                "proposal_id": str(proposal_id)}

    def create_plan(self, proposal_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        *, actor: str, baseline_start: date, baseline_end: date,
        observation_start: date, observation_end: date,
        primary_signals: list[str] | None = None) -> SEOMeasurementPlan:
        gate = self.eligibility(proposal_id, tenant_id, site_id)
        if not gate["eligible"]:
            raise SEOMeasurementError("Measurement eligibility failed: " + "; ".join(
                item["reason"] for item in gate["failed_gates"]))
        if not baseline_start <= baseline_end < observation_start <= observation_end:
            raise SEOMeasurementError("Baseline and observation windows must be ordered and non-overlapping.")
        proposal = self.session.get_one(PageChangeProposal, proposal_id)
        brief = self.session.get_one(ContentBrief, proposal.content_brief_id)
        investigation = self.session.get_one(SEOInvestigation, proposal.investigation_id)
        market = self.session.get_one(MarketDefinition, investigation.market_definition_id)
        signals = primary_signals or ["GSC_CLICKS", "GSC_IMPRESSIONS"]
        allowed = {"GSC_CLICKS", "GSC_IMPRESSIONS", "GSC_CTR", "GSC_AVERAGE_POSITION"}
        if not signals or not set(signals) <= allowed:
            raise SEOMeasurementError("Unsupported or empty primary measurement signals.")
        identity = _digest([proposal.id, proposal.evidence_fingerprint, baseline_start,
                            baseline_end, observation_start, observation_end, sorted(signals)])
        existing = self.session.scalar(select(SEOMeasurementPlan).where(
            SEOMeasurementPlan.identity_hash == identity))
        if existing:
            return existing
        previous = self.session.scalar(select(SEOMeasurementPlan).where(
            SEOMeasurementPlan.proposal_id == proposal.id).order_by(
                SEOMeasurementPlan.created_at.desc(), SEOMeasurementPlan.id.desc()))
        plan = SEOMeasurementPlan(tenant_id=tenant_id, site_id=site_id,
            investigation_id=investigation.id, content_brief_id=brief.id,
            proposal_id=proposal.id, query_entity_id=brief.query_entity_id,
            page_entity_id=brief.page_entity_id, market_definition_id=brief.market_definition_id,
            exact_query=brief.exact_query, candidate_url=brief.candidate_url,
            status="AWAITING_BASELINE", measurement_method=METHOD, method_version=VERSION,
            previous_plan_id=previous.id if previous else None, identity_hash=identity,
            created_by=actor, baseline_start=baseline_start, baseline_end=baseline_end,
            observation_start=observation_start, observation_end=observation_end,
            minimum_observation_guidance="Require observations in both windows and at least 10 impressions per window; low volume remains insufficient.",
            primary_signals_json=signals, secondary_signals_json=["GSC_CTR", "GSC_AVERAGE_POSITION"],
            guardrail_signals_json=["QUERY_PAGE_SCOPE", "OWNED_PAGE_FINGERPRINT"],
            required_sources_json=["GOOGLE_SEARCH_CONSOLE"],
            scope_dimensions_json={"country": market.country_code, "language": market.language_code,
                "device": market.device, "search_engine": "google", "search_type": "web"},
            expected_direction="INCREASE", null_expectation="No material observed change is plausible.",
            confounders_json=["Algorithm changes", "SERP composition", "seasonality", "concurrent site changes"],
            risks_json=["Low volume", "Incomplete instrumentation", "Average-position aggregation semantics"],
            assumptions_json=["GSC observations use compatible query/page dimensions."],
            limitations_json=["Observational comparison cannot establish causality.",
                "SERP non-observation beyond collected depth is not zero."],
            decision_rule="Classify only observed direction across compatible windows; mixed signals remain conflicting.",
            human_review_requirements_json=["IMPLEMENTATION_VERIFICATION", "OUTCOME_INTERPRETATION"],
            readiness_state="AWAITING_BASELINE")
        self.session.add(plan)
        self.session.flush()
        return plan

    def scoped_plan(self, plan_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> SEOMeasurementPlan:
        plan = self.session.get(SEOMeasurementPlan, plan_id)
        if not plan or plan.tenant_id != tenant_id or plan.site_id != site_id:
            raise SEOMeasurementError("Measurement plan not found in tenant/site scope.")
        return plan

    def plans(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> list[SEOMeasurementPlan]:
        return list(self.session.scalars(select(SEOMeasurementPlan).where(
            SEOMeasurementPlan.investigation_id == investigation_id,
            SEOMeasurementPlan.tenant_id == tenant_id, SEOMeasurementPlan.site_id == site_id
        ).order_by(SEOMeasurementPlan.created_at.desc(), SEOMeasurementPlan.id.desc())))

    def compatible_gsc(self, plan: SEOMeasurementPlan) -> list[GSCSearchObservation]:
        scope = plan.scope_dimensions_json
        rows = list(self.session.scalars(select(GSCSearchObservation).where(
            GSCSearchObservation.tenant_id == plan.tenant_id,
            GSCSearchObservation.site_id == plan.site_id,
            GSCSearchObservation.observed_date >= plan.baseline_start,
            GSCSearchObservation.observed_date <= plan.observation_end,
            GSCSearchObservation.effective_end.is_(None),
        ).order_by(GSCSearchObservation.observed_date, GSCSearchObservation.id)))
        compatible = []
        for row in rows:
            connection = self.session.get(DataSourceConnection, row.data_source_connection_id)
            connection_scope = connection.configuration_json if connection else {}
            country = row.country or connection_scope.get("country")
            device = row.device or connection_scope.get("device")
            if (row.query and row.page
                    and normalize_query(row.query) == normalize_query(plan.exact_query)
                    and normalize_url(row.page) == normalize_url(plan.candidate_url)
                    and country and country.casefold() == str(scope["country"]).casefold()
                    and device and device.casefold() == str(scope["device"]).casefold()
                    and row.search_type.casefold() == str(scope["search_type"]).casefold()
                    and row.quality_flag is not QualityFlag.INVALID):
                rights = self.session.get(DataRightsPolicy, row.rights_policy_id)
                if rights and rights.deterministic_analysis_allowed is RightsDecision.ALLOWED \
                        and rights.derived_storage_allowed is RightsDecision.ALLOWED:
                    compatible.append(row)
        return compatible

    def baseline_readiness(self, plan: SEOMeasurementPlan) -> dict[str, Any]:
        rows = [row for row in self.compatible_gsc(plan)
                if plan.baseline_start <= row.observed_date <= plan.baseline_end]
        impressions = sum((row.impressions for row in rows), Decimal(0))
        ready = bool(rows) and impressions >= 10
        return {"ready": ready, "state": "BASELINE_READY" if ready else "AWAITING_BASELINE",
                "observation_count": len(rows), "impressions": str(impressions)}

    def record_implementation(self, plan_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID, *, actor: str, state: str,
        claimed_at: datetime | None, deployment_reference: str | None,
        categories: list[str], deviations: list[str], concurrent_changes: list[str],
        rollback_reference: str | None = None, notes: str | None = None,
        artifact_references: list[str] | None = None) -> SEOImplementationRecord:
        plan = self.scoped_plan(plan_id, tenant_id, site_id)
        proposal = self.session.get_one(PageChangeProposal, plan.proposal_id)
        if state not in IMPLEMENTATION_STATES:
            raise SEOMeasurementError("Unsupported implementation state.")
        if state in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "ROLLED_BACK"} and not claimed_at:
            raise SEOMeasurementError("This implementation state requires an explicit timestamp.")
        if claimed_at and claimed_at.tzinfo is None:
            raise SEOMeasurementError("Implementation timestamp must include a timezone.")
        if claimed_at and claimed_at.date() <= plan.baseline_end:
            raise SEOMeasurementError("Implementation timestamp must follow the baseline window.")
        if (claimed_at and state in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}
                and claimed_at.date() >= plan.observation_start):
            raise SEOMeasurementError("Implementation timestamp must precede the observation window.")
        if state in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED"} and (
                not categories or proposal.category not in categories):
            raise SEOMeasurementError("Implemented categories do not include the approved proposal category.")
        record = SEOImplementationRecord(measurement_plan_id=plan.id, proposal_id=proposal.id,
            tenant_id=tenant_id, site_id=site_id, candidate_url=plan.candidate_url,
            actor=actor, implementation_state=state, claimed_implementation_at=claimed_at,
            recorded_at=_now(), deployment_reference=deployment_reference,
            implemented_categories_json=categories, deviations_json=deviations,
            concurrent_changes_json=concurrent_changes, rollback_reference=rollback_reference,
            notes=notes, artifact_references_json=artifact_references or [],
            verification_state="VERIFICATION_REQUIRED", reviewer=None, reviewed_at=None)
        self.session.add(record)
        self.session.flush()
        if claimed_at and state in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}:
            plan.implementation_at = claimed_at
            plan.status = "OBSERVATION_WINDOW_OPEN"
            plan.readiness_state = "OBSERVATION_WINDOW_OPEN"
        return record

    def implementation_records(self, plan: SEOMeasurementPlan) -> list[SEOImplementationRecord]:
        return list(self.session.scalars(select(SEOImplementationRecord).where(
            SEOImplementationRecord.measurement_plan_id == plan.id).order_by(
                SEOImplementationRecord.recorded_at, SEOImplementationRecord.id)))

    def assess(self, plan_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        *, as_of: datetime, evidence_reference_ids: list[uuid.UUID]) -> SEOOutcomeAssessment:
        plan = self.scoped_plan(plan_id, tenant_id, site_id)
        if as_of.tzinfo is None:
            raise SEOMeasurementError("Assessment timestamp must include a timezone.")
        implementations = self.implementation_records(plan)
        implementation = implementations[-1] if implementations else None
        if not implementation or implementation.implementation_state not in {
            "IMPLEMENTED", "PARTIALLY_IMPLEMENTED"}:
            raise SEOMeasurementError("Explicit implemented or partially implemented record is required.")
        rows_by_id = {row.id: row for row in self.compatible_gsc(plan)}
        unknown = set(evidence_reference_ids) - set(rows_by_id)
        if unknown:
            raise SEOMeasurementError("Unknown, rights-blocked, or scope-incompatible evidence reference.")
        selected = [rows_by_id[value] for value in sorted(set(evidence_reference_ids), key=str)]
        baseline = [row for row in selected if plan.baseline_start <= row.observed_date <= plan.baseline_end]
        post = [row for row in selected if plan.observation_start <= row.observed_date <= plan.observation_end]
        contaminated = [row for row in selected if plan.baseline_end < row.observed_date < plan.observation_start]
        if contaminated:
            raise SEOMeasurementError("Implementation-window or post-change evidence cannot be used as baseline.")
        comparisons = self._compare(baseline, post)
        baseline_impressions = sum((row.impressions for row in baseline), Decimal(0))
        post_impressions = sum((row.impressions for row in post), Decimal(0))
        if not baseline or baseline_impressions < 10:
            outcome = "INSUFFICIENT_DATA"
        elif as_of.date() < plan.observation_end:
            outcome = "OBSERVATION_WINDOW_OPEN"
        elif not post:
            outcome = "AWAITING_POST_CHANGE_DATA"
        elif post_impressions < 10:
            outcome = "INSUFFICIENT_DATA"
        else:
            directions = {item["direction"] for item in comparisons if item["signal"] in plan.primary_signals_json}
            outcome = ("MIXED_OR_CONFLICTING" if len(directions) > 1 else
                {"INCREASE": "OBSERVED_INCREASE", "DECREASE": "OBSERVED_DECREASE",
                 "STABLE": "OBSERVED_STABILITY"}.get(next(iter(directions), "STABLE"), "INCONCLUSIVE"))
        fingerprint = _digest([plan.identity_hash, implementation.id,
            [(row.id, row.observation_key, row.clicks, row.impressions, row.ctr, row.position)
             for row in selected], as_of.date()])
        existing = self.session.scalar(select(SEOOutcomeAssessment).where(
            SEOOutcomeAssessment.input_fingerprint == fingerprint))
        if existing:
            return existing
        previous = self.session.scalar(select(SEOOutcomeAssessment).where(
            SEOOutcomeAssessment.measurement_plan_id == plan.id).order_by(
                SEOOutcomeAssessment.assessed_at.desc(), SEOOutcomeAssessment.id.desc()))
        limitations = list(plan.limitations_json)
        if implementation.implementation_state == "PARTIALLY_IMPLEMENTED":
            limitations.append("Implementation was explicitly recorded as partial.")
        if implementation.concurrent_changes_json:
            limitations.append("Concurrent changes limit interpretation.")
        investigation = self.session.get_one(SEOInvestigation, plan.investigation_id)
        package_ids = ContentBriefService(self.session).context(investigation)["package_ids"]
        assessment = SEOOutcomeAssessment(measurement_plan_id=plan.id,
            implementation_record_id=implementation.id,
            previous_assessment_id=previous.id if previous else None,
            input_fingerprint=fingerprint, assessed_at=as_of,
            window_start=plan.observation_start, window_end=plan.observation_end,
            outcome_state=outcome, primary_result_json=comparisons[0] if comparisons else {},
            secondary_results_json=comparisons[1:], guardrail_results_json=[],
            evidence_package_ids_json=[str(value) for value in package_ids],
            evidence_reference_ids_json=[str(row.id) for row in selected],
            scope_result="COMPATIBLE", rights_result="USABLE", quality_result=(
                "LIMITED" if any(row.quality_flag is not QualityFlag.VALID for row in selected) else "SUPPORTED"),
            completeness_result=("SUPPORTED" if baseline and post else "INCOMPLETE"),
            conflict_state="CONFLICTING" if outcome == "MIXED_OR_CONFLICTING" else "NONE",
            confounders_json=plan.confounders_json,
            concurrent_changes_json=implementation.concurrent_changes_json,
            comparisons_json=comparisons,
            bounded_interpretation=f"{outcome.replace('_', ' ').title()} was observed in the bounded windows. Causality is not established.",
            causal_classification="CAUSALITY_NOT_ESTABLISHED",
            assumptions_json=plan.assumptions_json, limitations_json=limitations,
            remaining_needs_json=[] if outcome.startswith("OBSERVED_") else ["Continue compatible observation."],
            recommended_next_action=("Human review may consider explicit closure."
                if outcome.startswith("OBSERVED_") else "Continue observing or gather compatible evidence."),
            continued_observation_required=not outcome.startswith("OBSERVED_"),
            human_review_required=True, closure_eligible=outcome.startswith("OBSERVED_"))
        self.session.add(assessment)
        self.session.flush()
        plan.status = outcome
        plan.readiness_state = outcome
        return assessment

    def _compare(self, baseline: list[GSCSearchObservation],
        post: list[GSCSearchObservation]) -> list[dict[str, Any]]:
        def totals(rows: list[GSCSearchObservation]) -> dict[str, Decimal]:
            impressions = sum((row.impressions for row in rows), Decimal(0))
            clicks = sum((row.clicks for row in rows), Decimal(0))
            ctr = clicks / impressions if impressions else Decimal(0)
            position = (sum((row.position * row.impressions for row in rows), Decimal(0)) /
                        impressions if impressions else Decimal(0))
            return {"GSC_CLICKS": clicks, "GSC_IMPRESSIONS": impressions,
                    "GSC_CTR": ctr, "GSC_AVERAGE_POSITION": position}
        before, after = totals(baseline), totals(post)
        results = []
        for signal in ("GSC_CLICKS", "GSC_IMPRESSIONS", "GSC_CTR", "GSC_AVERAGE_POSITION"):
            old, new = before[signal], after[signal]
            absolute = new - old
            relative = ((new - old) / old) if old else None
            effective = -absolute if signal == "GSC_AVERAGE_POSITION" else absolute
            threshold = abs(old) * Decimal("0.05")
            direction = "STABLE" if abs(effective) <= threshold else (
                "INCREASE" if effective > 0 else "DECREASE")
            results.append({"signal": signal, "baseline": str(old), "post": str(new),
                "absolute_change": str(absolute),
                "relative_change": str(relative) if relative is not None else None,
                "direction": direction, "baseline_observations": len(baseline),
                "post_observations": len(post), "method_version": VERSION})
        return results

    def assessments(self, plan: SEOMeasurementPlan) -> list[SEOOutcomeAssessment]:
        return list(self.session.scalars(select(SEOOutcomeAssessment).where(
            SEOOutcomeAssessment.measurement_plan_id == plan.id).order_by(
                SEOOutcomeAssessment.assessed_at.desc(), SEOOutcomeAssessment.id.desc())))

    def scoped_assessment(self, assessment_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> SEOOutcomeAssessment:
        assessment = self.session.get(SEOOutcomeAssessment, assessment_id)
        if not assessment:
            raise SEOMeasurementError("Outcome assessment was not found.")
        self.scoped_plan(assessment.measurement_plan_id, tenant_id, site_id)
        return assessment

    def review(self, plan_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        *, artifact_type: str, artifact_id: uuid.UUID, reviewer: str,
        decision: str, comment: str | None, follow_up: list[str]) -> SEOMeasurementReview:
        plan = self.scoped_plan(plan_id, tenant_id, site_id)
        if decision not in REVIEW_DECISIONS or not reviewer.strip():
            raise SEOMeasurementError("Valid reviewer and decision are required.")
        implementation = self.session.get(SEOImplementationRecord, artifact_id)
        outcome = self.session.get(SEOOutcomeAssessment, artifact_id)
        valid = (artifact_type == "PLAN" and artifact_id == plan.id) or (
            artifact_type == "IMPLEMENTATION" and implementation is not None
            and implementation.measurement_plan_id == plan.id) or (
            artifact_type == "OUTCOME" and outcome is not None
            and outcome.measurement_plan_id == plan.id)
        if not valid:
            raise SEOMeasurementError("Reviewed artifact is not in this measurement plan.")
        review = SEOMeasurementReview(measurement_plan_id=plan.id,
            artifact_type=artifact_type, artifact_id=artifact_id, reviewer=reviewer,
            decision=decision, comment=comment, evidence_fingerprint=plan.identity_hash,
            requested_follow_up_json=follow_up, reviewed_at=_now())
        self.session.add(review)
        if decision == "CLOSE_INVESTIGATION":
            latest = self.assessments(plan)
            if not latest or not latest[0].closure_eligible:
                raise SEOMeasurementError("Outcome is not eligible for explicit closure.")
            plan.status = "CLOSED"
            plan.readiness_state = "CLOSED"
        self.session.flush()
        return review

    def reopen(self, plan_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        *, actor: str, reason: str) -> SEOMeasurementReview:
        plan = self.scoped_plan(plan_id, tenant_id, site_id)
        if plan.status != "CLOSED":
            raise SEOMeasurementError("Only a closed measurement workflow can be reopened.")
        review = SEOMeasurementReview(measurement_plan_id=plan.id,
            artifact_type="PLAN", artifact_id=plan.id, reviewer=actor,
            decision="APPROVE_FOLLOW_UP", comment=reason,
            evidence_fingerprint=plan.identity_hash,
            requested_follow_up_json=["REOPENED"], reviewed_at=_now())
        self.session.add(review)
        latest = self.assessments(plan)
        plan.status = latest[0].outcome_state if latest else "AWAITING_BASELINE"
        plan.readiness_state = plan.status
        self.session.flush()
        return review

    def plan_model(self, plan: SEOMeasurementPlan) -> dict[str, Any]:
        implementations = self.implementation_records(plan)
        assessments = self.assessments(plan)
        reviews = list(self.session.scalars(select(SEOMeasurementReview).where(
            SEOMeasurementReview.measurement_plan_id == plan.id).order_by(
            SEOMeasurementReview.reviewed_at, SEOMeasurementReview.id)))
        baseline = self.baseline_readiness(plan)
        return {"id": str(plan.id), "investigation_id": str(plan.investigation_id),
            "proposal_id": str(plan.proposal_id), "status": plan.status,
            "readiness": plan.readiness_state, "exact_query": plan.exact_query,
            "candidate_url": plan.candidate_url, "market_id": str(plan.market_definition_id),
            "implementation": ({"state": implementations[-1].implementation_state,
                "claimed_at": implementations[-1].claimed_implementation_at.isoformat()
                if implementations[-1].claimed_implementation_at else None,
                "deviations": implementations[-1].deviations_json,
                "concurrent_changes": implementations[-1].concurrent_changes_json,
                "verification": implementations[-1].verification_state} if implementations else
                {"state": "NOT_IMPLEMENTED"}), "baseline": baseline,
            "observation_window": {"start": plan.observation_start.isoformat(),
                "end": plan.observation_end.isoformat()},
            "primary_signals": plan.primary_signals_json,
            "secondary_signals": plan.secondary_signals_json,
            "guardrails": plan.guardrail_signals_json,
            "current_outcome": self.assessment_model(assessments[0]) if assessments else None,
            "human_reviews": [{"id": str(item.id), "artifact_type": item.artifact_type,
                "artifact_id": str(item.artifact_id), "reviewer": item.reviewer,
                "decision": item.decision, "comment": item.comment,
                "reviewed_at": item.reviewed_at.isoformat(),
                "follow_up": item.requested_follow_up_json} for item in reviews],
            "limitations": plan.limitations_json, "confounders": plan.confounders_json,
            "next_action": self.next_action(plan, bool(implementations), baseline["ready"],
                                             assessments[0] if assessments else None),
            "technical": {"identity_hash": plan.identity_hash, "method": VERSION,
                "content_brief_id": str(plan.content_brief_id),
                "previous_plan_id": str(plan.previous_plan_id) if plan.previous_plan_id else None}}

    def next_action(self, plan: SEOMeasurementPlan, implemented: bool,
        baseline_ready: bool, assessment: SEOOutcomeAssessment | None) -> dict[str, str]:
        if plan.status == "CLOSED":
            return {"type": "REOPEN", "label": "Reopen measurement workflow"}
        if not baseline_ready:
            return {"type": "ESTABLISH_BASELINE", "label": "Gather compatible baseline evidence"}
        if not implemented:
            return {"type": "CONFIRM_IMPLEMENTATION", "label": "Record implementation explicitly"}
        if assessment is None:
            return {"type": "RUN_OUTCOME_ASSESSMENT", "label": "Run deterministic outcome assessment"}
        if assessment.human_review_required:
            return {"type": "REVIEW_OUTCOME", "label": "Review bounded outcome"}
        return {"type": "CONTINUE_OBSERVING", "label": "Continue governed observation"}

    def assessment_model(self, item: SEOOutcomeAssessment) -> dict[str, Any]:
        return {"id": str(item.id), "outcome": item.outcome_state,
            "interpretation": item.bounded_interpretation,
            "causal_classification": item.causal_classification,
            "comparisons": item.comparisons_json, "quality": item.quality_result,
            "completeness": item.completeness_result, "conflicts": item.conflict_state,
            "limitations": item.limitations_json, "next_action": item.recommended_next_action,
            "closure_eligible": item.closure_eligible}
