from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from gis.collection_planning.service import normalize_target
from gis.evidence_quality.analysis import normalize_url as normalize_identity_url
from gis.models import (
    AnalyticalEntity,
    AnalyticalEntityType,
    CollectionPriorityTier,
    CollectionRequirement,
    CollectionRequirementStatus,
    CollectionTargetType,
    EvidenceGap,
    EvidenceGapAdjudication,
    EvidenceGapAdjudicationReview,
    EvidencePackage,
    ExactQuerySerpSnapshotDetail,
    ExperimentProposal,
    MarketDefinition,
    OwnedSurfaceObservationDetail,
    QueryPageIntentAssessment,
    QueryPageIntentReview,
    Recommendation,
    SEOInvestigation,
    SEOInvestigationEvent,
)

ACTIVE_STATES = {
    "DRAFT", "EVIDENCE_REQUIRED", "AWAITING_COLLECTION_APPROVAL",
    "COLLECTION_CANDIDATE", "AWAITING_ADJUDICATION", "CONFLICTING_EVIDENCE",
    "AWAITING_HUMAN_REVIEW", "READY_FOR_INTERPRETATION",
    "READY_FOR_RECOMMENDATION", "BLOCKED",
}
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
SEVERITY_ORDER = {"BLOCKED": 0, "CONFLICTING_EVIDENCE": 1, "EVIDENCE_REQUIRED": 2,
                  "AWAITING_HUMAN_REVIEW": 3, "AWAITING_ADJUDICATION": 4}


class SEOInvestigationError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _digest(values: object) -> str:
    return hashlib.sha256(json.dumps(values, default=str, sort_keys=True).encode()).hexdigest()


class SEOInvestigationService:
    """Guided, deterministic orchestration over existing governed intelligence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, tenant_id: uuid.UUID, site_id: uuid.UUID,
        query_entity_id: uuid.UUID, candidate_page_entity_id: uuid.UUID,
        market_definition_id: uuid.UUID, exact_query: str, candidate_url: str,
        title: str, question: str, priority: CollectionPriorityTier,
        actor: str, origin: str = "OPERATOR", originating_proposal_id: uuid.UUID | None = None,
        originating_recommendation_id: uuid.UUID | None = None) -> SEOInvestigation:
        query = self._entity(query_entity_id, tenant_id, site_id, AnalyticalEntityType.QUERY)
        page = self._entity(candidate_page_entity_id, tenant_id, site_id, AnalyticalEntityType.URL)
        market = self.session.get(MarketDefinition, market_definition_id)
        if not market or market.tenant_id != tenant_id or market.site_id != site_id:
            raise SEOInvestigationError("Market definition is outside tenant/site scope.")
        normalized_query, _ = normalize_target(CollectionTargetType.QUERY, exact_query)
        governed_query, _ = normalize_target(CollectionTargetType.QUERY, query.canonical_key)
        parsed_url = urlsplit(candidate_url.strip())
        if parsed_url.scheme.casefold() not in {"http", "https"} or not parsed_url.hostname:
            raise SEOInvestigationError("Candidate URL must be an absolute HTTP(S) URL.")
        normalized_url = normalize_identity_url(candidate_url)
        governed_url = normalize_identity_url(page.canonical_key)
        if normalized_query != governed_query:
            raise SEOInvestigationError("Exact query differs from governed query identity.")
        if normalized_url != governed_url:
            raise SEOInvestigationError("Candidate URL differs from governed page identity.")
        for actual, expected, label in (
            (query.country_code, market.country_code, "country"),
            (query.language_code, market.language_code, "language"),
            (query.device, market.device, "device"),
        ):
            if actual and actual.casefold() != expected.casefold():
                raise SEOInvestigationError(f"Query {label} is incompatible with the market.")
        reference: Any
        for reference_id, model, label in (
            (originating_proposal_id, ExperimentProposal, "proposal"),
            (originating_recommendation_id, Recommendation, "recommendation"),
        ):
            if reference_id is None:
                continue
            reference = self.session.get(model, reference_id)
            if (not reference or reference.tenant_id != tenant_id
                    or reference.site_id != site_id):
                raise SEOInvestigationError(
                    f"Originating {label} is outside tenant/site scope."
                )
        identity = _digest([tenant_id, site_id, query.id, page.id, market.id])
        existing = self.session.scalar(select(SEOInvestigation).where(
            SEOInvestigation.identity_hash == identity, SEOInvestigation.closed_at.is_(None)))
        if existing:
            return existing
        row = SEOInvestigation(
            tenant_id=tenant_id, site_id=site_id, query_entity_id=query.id,
            candidate_page_entity_id=page.id, market_definition_id=market.id,
            exact_query=normalized_query, normalized_candidate_url=normalized_url,
            title=title, question=question, lifecycle_state="DRAFT", priority=priority,
            origin=origin, created_by=actor, evidence_readiness_state="NOT_EVALUATED",
            human_review_required=False, recommendation_generation_eligible=False,
            identity_hash=identity, originating_proposal_id=originating_proposal_id,
            originating_recommendation_id=originating_recommendation_id,
        )
        self.session.add(row)
        self.session.flush()
        snapshot = self.snapshot(row)
        self._apply_derived(row, snapshot, actor, "CREATED", "Investigation scope was created.")
        return row

    def _entity(self, entity_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        expected: AnalyticalEntityType) -> AnalyticalEntity:
        row = self.session.get(AnalyticalEntity, entity_id)
        if not row or row.tenant_id != tenant_id or row.site_id != site_id:
            raise SEOInvestigationError("Analytical entity is outside tenant/site scope.")
        if row.entity_type is not expected:
            raise SEOInvestigationError(f"Expected a governed {expected.value} entity.")
        return row

    def scoped(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> SEOInvestigation:
        row = self.session.get(SEOInvestigation, investigation_id)
        if not row or row.tenant_id != tenant_id or row.site_id != site_id:
            raise SEOInvestigationError("SEO investigation not found in tenant/site scope.")
        return row

    def snapshot(self, row: SEOInvestigation) -> dict[str, Any]:
        gaps = list(self.session.scalars(select(EvidenceGap).join(
            EvidencePackage, EvidencePackage.id == EvidenceGap.evidence_package_id).where(
                EvidencePackage.tenant_id == row.tenant_id,
                EvidencePackage.site_id == row.site_id,
                EvidencePackage.analytical_entity_id == row.query_entity_id,
                or_(EvidencePackage.market_definition_id == row.market_definition_id,
                    EvidencePackage.market_definition_id.is_(None)),
            ).order_by(EvidenceGap.created_at, EvidenceGap.id)))
        gap_ids = [gap.id for gap in gaps]
        adjudications = list(self.session.scalars(select(EvidenceGapAdjudication).where(
            EvidenceGapAdjudication.evidence_gap_id.in_(gap_ids),
            EvidenceGapAdjudication.is_current.is_(True)).order_by(
                EvidenceGapAdjudication.evaluated_at, EvidenceGapAdjudication.id))) if gap_ids else []
        adjudication_by_gap = {item.evidence_gap_id: item for item in adjudications}
        requirements = list(self.session.scalars(select(CollectionRequirement).where(
            CollectionRequirement.evidence_gap_id.in_(gap_ids)).order_by(
                CollectionRequirement.created_at, CollectionRequirement.id))) if gap_ids else []
        assessment = self.session.scalar(select(QueryPageIntentAssessment).where(
            QueryPageIntentAssessment.tenant_id == row.tenant_id,
            QueryPageIntentAssessment.site_id == row.site_id,
            QueryPageIntentAssessment.query_entity_id == row.query_entity_id,
            QueryPageIntentAssessment.page_entity_id == row.candidate_page_entity_id,
            QueryPageIntentAssessment.market_definition_id == row.market_definition_id,
            QueryPageIntentAssessment.is_current.is_(True)).order_by(
                QueryPageIntentAssessment.evaluated_at.desc(), QueryPageIntentAssessment.id.desc()))
        assessment_review = self.session.scalar(select(QueryPageIntentReview).where(
            QueryPageIntentReview.assessment_id == assessment.id).order_by(
                QueryPageIntentReview.reviewed_at.desc(), QueryPageIntentReview.id.desc())) if assessment else None
        adjudication_reviews = {}
        if adjudications:
            reviews = list(self.session.scalars(select(EvidenceGapAdjudicationReview).where(
                EvidenceGapAdjudicationReview.adjudication_id.in_([item.id for item in adjudications])
            ).order_by(EvidenceGapAdjudicationReview.reviewed_at, EvidenceGapAdjudicationReview.id)))
            for review in reviews:
                adjudication_reviews[review.adjudication_id] = review
        owned_count = self.session.scalar(select(func.count()).select_from(
            OwnedSurfaceObservationDetail).join(
                EvidencePackage,
                EvidencePackage.id == OwnedSurfaceObservationDetail.evidence_package_id,
            ).where(
                EvidencePackage.tenant_id == row.tenant_id,
                EvidencePackage.site_id == row.site_id,
                EvidencePackage.analytical_entity_id == row.query_entity_id,
                or_(EvidencePackage.market_definition_id == row.market_definition_id,
                    EvidencePackage.market_definition_id.is_(None)),
            )) or 0
        serp_count = self.session.scalar(select(func.count()).select_from(
            ExactQuerySerpSnapshotDetail).where(
                ExactQuerySerpSnapshotDetail.analytical_entity_id == row.query_entity_id,
                ExactQuerySerpSnapshotDetail.market_definition_id == row.market_definition_id)) or 0
        outcomes = [item.outcome for item in adjudications]
        unresolved = [gap for gap in gaps if not adjudication_by_gap.get(gap.id)
                      or adjudication_by_gap[gap.id].outcome != "SATISFIED"]
        human_required = bool(assessment and not assessment_review) or any(
            item.human_review_required and (
                not adjudication_reviews.get(item.id)
                or adjudication_reviews[item.id].decision != "CONFIRM") for item in adjudications)
        all_satisfied = bool(gaps) and not unresolved
        intent_supported = bool(assessment and assessment.targeting_state == "SUPPORTED"
                                and assessment.intent_satisfaction_state == "SUPPORTED")
        gates_pass = all_satisfied and intent_supported and not human_required
        if row.closed_at:
            stage = row.lifecycle_state
        elif "BLOCKED" in outcomes:
            stage = "BLOCKED"
        elif "CONFLICTING_EVIDENCE" in outcomes:
            stage = "CONFLICTING_EVIDENCE"
        elif not gaps:
            stage = "EVIDENCE_REQUIRED"
        elif any(gap.id not in adjudication_by_gap for gap in gaps):
            statuses = {requirement.status for requirement in requirements}
            if statuses & {CollectionRequirementStatus.BLOCKED,
                           CollectionRequirementStatus.UNSUPPORTED}:
                stage = "BLOCKED"
            elif CollectionRequirementStatus.REQUESTED in statuses:
                stage = "AWAITING_COLLECTION_APPROVAL"
            elif CollectionRequirementStatus.CANDIDATE in statuses:
                stage = "COLLECTION_CANDIDATE"
            elif statuses & {CollectionRequirementStatus.APPLIED,
                             CollectionRequirementStatus.COLLECTING}:
                stage = "EVIDENCE_REQUIRED"
            else:
                stage = "AWAITING_ADJUDICATION"
        elif unresolved:
            stage = "EVIDENCE_REQUIRED"
        elif not assessment:
            stage = "READY_FOR_INTERPRETATION"
        elif human_required:
            stage = "AWAITING_HUMAN_REVIEW"
        elif not intent_supported:
            stage = "EVIDENCE_REQUIRED"
        elif row.lifecycle_state == "READY_FOR_RECOMMENDATION":
            stage = "READY_FOR_RECOMMENDATION"
        else:
            stage = "READY_FOR_INTERPRETATION"
        readiness = "SUPPORTED" if gates_pass else (
            "CONFLICTING" if "CONFLICTING_EVIDENCE" in outcomes else
            "BLOCKED" if "BLOCKED" in outcomes else
            "LIMITED" if outcomes else "MISSING")
        return {"stage": stage, "readiness": readiness, "gaps": gaps,
                "adjudications": adjudications, "adjudication_by_gap": adjudication_by_gap,
                "requirements": requirements, "assessment": assessment,
                "assessment_review": assessment_review, "adjudication_reviews": adjudication_reviews,
                "owned_count": owned_count, "serp_count": serp_count,
                "human_required": human_required, "gates_pass": gates_pass}

    def _apply_derived(self, row: SEOInvestigation, snapshot: dict[str, Any], actor: str,
        event_type: str, reason: str) -> None:
        previous = row.lifecycle_state
        row.lifecycle_state = snapshot["stage"]
        row.evidence_readiness_state = snapshot["readiness"]
        row.human_review_required = snapshot["human_required"]
        row.recommendation_generation_eligible = (
            snapshot["gates_pass"] and row.lifecycle_state == "READY_FOR_RECOMMENDATION")
        assessment = snapshot["assessment"]
        row.current_query_page_intent_assessment_id = assessment.id if assessment else None
        adjudications = snapshot["adjudications"]
        row.current_evidence_gap_adjudication_id = adjudications[-1].id if adjudications else None
        self.session.add(SEOInvestigationEvent(
            investigation_id=row.id, actor=actor, event_type=event_type,
            previous_state=previous, new_state=row.lifecycle_state, reason=reason,
            adjudication_id=row.current_evidence_gap_adjudication_id,
            assessment_id=row.current_query_page_intent_assessment_id,
            metadata_json={"evidence_readiness": row.evidence_readiness_state}, occurred_at=_now()))

    def action(self, row: SEOInvestigation, snapshot: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        state = snapshot or self.snapshot(row)
        stage = state["stage"]
        mapping = {
            "EVIDENCE_REQUIRED": ("GATHER_MORE_EVIDENCE", "Gather more governed evidence", "Evidence remains missing, limited, or insufficient."),
            "COLLECTION_CANDIDATE": ("REVIEW_COLLECTION", "Review candidate collection", "A candidate plan exists but collection is not authorized by this action."),
            "AWAITING_COLLECTION_APPROVAL": ("APPROVE_COLLECTION_REQUIREMENT", "Review collection requirement", "A requested collection requirement needs explicit operator approval."),
            "AWAITING_ADJUDICATION": ("RUN_GAP_ADJUDICATION", "Run deterministic gap adjudication", "Collected evidence must be adjudicated before interpretation."),
            "CONFLICTING_EVIDENCE": ("REVIEW_CONFLICTING_EVIDENCE", "Review conflicting evidence", "Governed evidence materially conflicts."),
            "BLOCKED": ("REVIEW_EVIDENCE_GAP", "Review blocked evidence", "A rights, scope, identity, method, or policy gate is blocking progress."),
            "READY_FOR_INTERPRETATION": (("MARK_READY_FOR_RECOMMENDATION", "Mark ready for recommendation", "All recommendation gates pass; explicit operator confirmation is required.") if state["gates_pass"] else ("RUN_QUERY_PAGE_INTENT", "Review query/page/intent interpretation", "Association, targeting, and intent satisfaction require governed interpretation.")),
            "AWAITING_HUMAN_REVIEW": ("REVIEW_INTERPRETATION", "Complete required human review", "A governed interpretation or adjudication awaits human confirmation."),
            "READY_FOR_RECOMMENDATION": ("REVIEW_RECOMMENDATION_READINESS", "Proceed to recommendation review", "The investigation is eligible, but recommendation generation remains explicit."),
            "CLOSED_NO_ACTION": ("REOPEN", "Reopen investigation", "The investigation is closed with no action."),
            "CLOSED": ("REOPEN", "Reopen investigation", "The investigation is closed."),
        }
        action_type, label, explanation = mapping.get(stage, ("COMPLETE_SCOPE", "Complete investigation scope", "The bounded scope is incomplete."))
        requirement = state["requirements"][0] if state["requirements"] else None
        return {"investigation_id": str(row.id), "title": row.title, "query": row.exact_query,
                "candidate_page": row.normalized_candidate_url, "stage": stage,
                "priority": row.priority.value, "action_type": action_type, "label": label,
                "explanation": explanation, "blocking_condition": None if state["gates_pass"] else stage,
                "requires_human_approval": action_type not in {"RUN_GAP_ADJUDICATION"},
                "may_incur_cost": bool(requirement and requirement.cost_class not in {"FREE_LOCAL", "UNKNOWN"}),
                "provider_or_capability": (requirement.provider_key or requirement.capability.value)
                if requirement else None,
                "target": requirement.target_value if requirement else row.normalized_candidate_url,
                "market_id": str(row.market_definition_id),
                "destination": f"/seo-investigations/{row.id}",
                "evidence_gap_id": str(requirement.evidence_gap_id) if requirement and requirement.evidence_gap_id else None,
                "requirement_id": str(requirement.id) if requirement else None,
                "adjudication_id": (str(state["adjudications"][-1].id)
                    if state["adjudications"] else None),
                "assessment_id": (str(state["assessment"].id)
                    if state["assessment"] else None),
                "detected_at": row.updated_at.isoformat() if row.updated_at else row.created_at.isoformat()}

    def read_model(self, row: SEOInvestigation) -> dict[str, Any]:
        state = self.snapshot(row)
        events = list(self.session.scalars(select(SEOInvestigationEvent).where(
            SEOInvestigationEvent.investigation_id == row.id).order_by(
                SEOInvestigationEvent.occurred_at, SEOInvestigationEvent.id)))
        return {"id": str(row.id), "label": row.title, "description": row.question,
                "status": state["stage"], "stage": state["stage"],
                "stage_explanation": self.action(row, state)["explanation"],
                "scope": {"exact_query": row.exact_query, "candidate_page": row.normalized_candidate_url,
                          "market_id": str(row.market_definition_id)},
                "next_action": self.action(row, state),
                "evidence_readiness": {"state": state["readiness"],
                    "owned_page_observations": state["owned_count"],
                    "exact_query_serp_observations": state["serp_count"]},
                "evidence_gaps": [{"id": str(gap.id), "type": gap.gap_type,
                    "description": gap.description, "resolved": gap.resolved_at is not None,
                    "adjudication": state["adjudication_by_gap"].get(gap.id).outcome
                    if state["adjudication_by_gap"].get(gap.id) else "NOT_ADJUDICATED"}
                    for gap in state["gaps"]],
                "query_page_intent": ({"id": str(state["assessment"].id),
                    "association": state["assessment"].association_state,
                    "targeting": state["assessment"].targeting_state,
                    "intent_satisfaction": state["assessment"].intent_satisfaction_state}
                    if state["assessment"] else {"status": "NOT_INTERPRETED"}),
                "human_review": {"required": state["human_required"],
                    "assessment_review": state["assessment_review"].decision
                    if state["assessment_review"] else "UNREVIEWED"},
                "recommendation_eligible": state["gates_pass"] and row.lifecycle_state == "READY_FOR_RECOMMENDATION",
                "history": [{"event_type": event.event_type, "actor": event.actor,
                    "previous_state": event.previous_state, "new_state": event.new_state,
                    "reason": event.reason, "occurred_at": event.occurred_at.isoformat()}
                    for event in events],
                "technical": {"investigation_id": str(row.id), "query_entity_id": str(row.query_entity_id),
                    "candidate_page_entity_id": str(row.candidate_page_entity_id),
                    "identity_hash": row.identity_hash,
                    "current_assessment_id": str(row.current_query_page_intent_assessment_id)
                    if row.current_query_page_intent_assessment_id else None,
                    "current_adjudication_id": str(row.current_evidence_gap_adjudication_id)
                    if row.current_evidence_gap_adjudication_id else None}}

    def apply(self, row: SEOInvestigation, action: str, actor: str, reason: str) -> SEOInvestigation:
        state = self.snapshot(row)
        if action == "MARK_READY_FOR_RECOMMENDATION":
            if not state["gates_pass"]:
                raise SEOInvestigationError("Recommendation readiness gates have not passed.")
            state["stage"] = "READY_FOR_RECOMMENDATION"
        elif action in {"CLOSE", "CLOSE_NO_ACTION"}:
            if not reason.strip():
                raise SEOInvestigationError("Closing an investigation requires a reason.")
            row.closed_at = _now()
            row.close_reason = reason
            state["stage"] = action.replace("CLOSE", "CLOSED")
        elif action == "REOPEN":
            if not row.closed_at:
                raise SEOInvestigationError("Only a closed investigation can be reopened.")
            row.closed_at = None
            row.close_reason = None
            state = self.snapshot(row)
        elif action == "REFRESH_READINESS":
            pass
        else:
            raise SEOInvestigationError("Unsupported investigation lifecycle action.")
        self._apply_derived(row, state, actor, action, reason)
        return row

    def inventory(self, tenant_id: uuid.UUID, site_id: uuid.UUID, *, search: str | None = None,
        stage: str | None = None, priority: str | None = None, market_id: uuid.UUID | None = None,
        readiness: str | None = None, human_review_required: bool | None = None,
        recommendation_eligible: bool | None = None, sort: str = "priority",
        order: str = "asc") -> list[dict[str, Any]]:
        filters = [SEOInvestigation.tenant_id == tenant_id, SEOInvestigation.site_id == site_id]
        if search:
            filters.append(or_(SEOInvestigation.title.ilike(f"%{search}%"),
                               SEOInvestigation.exact_query.ilike(f"%{search}%"),
                               SEOInvestigation.normalized_candidate_url.ilike(f"%{search}%")))
        if priority:
            filters.append(SEOInvestigation.priority == priority)
        if market_id:
            filters.append(SEOInvestigation.market_definition_id == market_id)
        rows = list(self.session.scalars(select(SEOInvestigation).where(*filters).order_by(
            SEOInvestigation.priority, SEOInvestigation.updated_at, SEOInvestigation.id)))
        items = []
        for row in rows:
            state = self.snapshot(row)
            eligible = state["gates_pass"] and row.lifecycle_state == "READY_FOR_RECOMMENDATION"
            if stage and state["stage"] != stage or readiness and state["readiness"] != readiness:
                continue
            if human_review_required is not None and state["human_required"] is not human_review_required:
                continue
            if recommendation_eligible is not None and eligible is not recommendation_eligible:
                continue
            items.append({"id": str(row.id), "label": row.title, "href": f"/seo-investigations/{row.id}",
                "query": row.exact_query, "candidate_page": row.normalized_candidate_url,
                "market_id": str(row.market_definition_id), "stage": state["stage"],
                "status": state["stage"], "priority": row.priority.value,
                "evidence_readiness": state["readiness"],
                "human_review_required": state["human_required"],
                "recommendation_eligible": eligible, "updated_at": row.updated_at.isoformat()})
        items.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 9),
            SEVERITY_ORDER.get(item["stage"], 9), item["updated_at"], item["id"]))
        if sort != "priority":
            items.sort(key=lambda item: (str(item.get(sort, "")), item["id"]),
                       reverse=order == "desc")
        elif order == "desc":
            items.reverse()
        return items

    def action_queue(self, tenant_id: uuid.UUID, site_id: uuid.UUID,
        investigation_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        filters = [SEOInvestigation.tenant_id == tenant_id,
                   SEOInvestigation.site_id == site_id]
        if investigation_id:
            filters.append(SEOInvestigation.id == investigation_id)
        rows = list(self.session.scalars(select(SEOInvestigation).where(*filters).order_by(
            SEOInvestigation.updated_at, SEOInvestigation.id)))
        actions = [self.action(row) for row in rows]
        actions.sort(key=lambda item: (PRIORITY_ORDER.get(item["priority"], 9),
            SEVERITY_ORDER.get(item["stage"], 9), item["detected_at"],
            item["investigation_id"], item["action_type"]))
        return actions
