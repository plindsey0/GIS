from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.models import (
    ContentBrief,
    ContentProposalReview,
    EvidenceGapAdjudicationEvidence,
    EvidencePackage,
    EvidencePackageItem,
    PageChangeProposal,
    RightsUsability,
    SEOInvestigation,
)
from gis.seo_investigations.service import SEOInvestigationService

METHOD_KEY = "GOVERNED_CONTENT_BRIEF"
METHOD_VERSION = "governed_content_brief_v1"
DECISIONS = {"APPROVE", "REJECT", "REQUEST_CHANGES", "NEEDS_MORE_EVIDENCE"}
PROHIBITED = (
    "will improve rankings", "will increase traffic", "will increase conversions",
    "will increase revenue", "google prefers", "guaranteed ranking", "users are confused",
    "calculator is accurate", "will create rich results",
)


class ContentBriefError(ValueError):
    pass


class StaleProposalError(ContentBriefError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ContentBriefService:
    """Provider-free governed editorial synthesis; never edits or publishes a page."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.investigations = SEOInvestigationService(session)

    def _investigation(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> SEOInvestigation:
        return self.investigations.scoped(investigation_id, tenant_id, site_id)

    def context(self, row: SEOInvestigation) -> dict[str, Any]:
        state = self.investigations.snapshot(row)
        adjudications = state["adjudications"]
        adjudication_ids = [item.id for item in adjudications]
        links = list(self.session.scalars(select(EvidenceGapAdjudicationEvidence).where(
            EvidenceGapAdjudicationEvidence.adjudication_id.in_(adjudication_ids)
        ))) if adjudication_ids else []
        package_ids = sorted({item.evidence_package_id for item in links}, key=str)
        packages = list(self.session.scalars(select(EvidencePackage).where(
            EvidencePackage.id.in_(package_ids)).order_by(EvidencePackage.created_at,
                EvidencePackage.id))) if package_ids else []
        items = list(self.session.scalars(select(EvidencePackageItem).where(
            EvidencePackageItem.evidence_package_id.in_(package_ids)).order_by(
                EvidencePackageItem.created_at, EvidencePackageItem.id))) if package_ids else []
        references = {str(item.evidence_reference_id) for item in items
                      if item.evidence_reference_id and item.rights_usability is RightsUsability.USABLE}
        assessment = state["assessment"]
        if assessment:
            for reference in assessment.supporting_references_json + assessment.conflicting_references_json:
                value = reference.get("reference_id")
                if value:
                    references.add(str(value))
        for adjudication in adjudications:
            references.update(adjudication.evidence_reference_ids_json)
        package_errors = []
        for package in packages:
            if package.tenant_id != row.tenant_id or package.site_id != row.site_id:
                package_errors.append(f"Evidence package {package.id} is outside tenant/site scope.")
            if package.analytical_entity_id != row.query_entity_id:
                package_errors.append(f"Evidence package {package.id} has incompatible query scope.")
            if package.market_definition_id not in {None, row.market_definition_id}:
                package_errors.append(f"Evidence package {package.id} has incompatible market scope.")
            if package.rights_usability is not RightsUsability.USABLE:
                package_errors.append(f"Evidence package {package.id} is not usable for derivatives.")
        fingerprint = _digest({
            "scope": [row.tenant_id, row.site_id, row.query_entity_id,
                      row.candidate_page_entity_id, row.market_definition_id,
                      row.exact_query, row.normalized_candidate_url],
            "packages": [(item.id, item.identity_hash) for item in packages],
            "adjudications": [(item.id, item.input_fingerprint, item.outcome,
                                item.is_current) for item in adjudications],
            "assessment": (assessment.id, assessment.input_fingerprint,
                           assessment.is_current) if assessment else None,
            "references": sorted(references),
        })
        return {**state, "packages": packages, "items": items,
                "package_ids": package_ids, "references": sorted(references),
                "package_errors": package_errors, "fingerprint": fingerprint}

    def eligibility(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> dict[str, Any]:
        row = self._investigation(investigation_id, tenant_id, site_id)
        context = self.context(row)
        failures: list[dict[str, str]] = []
        def fail(gate: str, reason: str) -> None:
            failures.append({"gate": gate, "reason": reason})
        if row.lifecycle_state != "READY_FOR_RECOMMENDATION":
            fail("INVESTIGATION_STATE", "Investigation was not explicitly marked ready for recommendation.")
        if not context["gaps"]:
            fail("EVIDENCE_GAPS", "No governed evidence-gap contract is linked.")
        if not context["adjudications"]:
            fail("ADJUDICATION", "Required evidence gaps have no current adjudication.")
        for adjudication in context["adjudications"]:
            if not adjudication.is_current or adjudication.outcome != "SATISFIED":
                fail("ADJUDICATION", f"Gap adjudication {adjudication.id} is {adjudication.outcome}.")
        assessment = context["assessment"]
        if not assessment:
            fail("QUERY_PAGE_INTENT", "A current query/page/intent assessment is required.")
        elif (assessment.query_entity_id != row.query_entity_id
              or assessment.page_entity_id != row.candidate_page_entity_id
              or assessment.market_definition_id != row.market_definition_id):
            fail("QUERY_PAGE_INTENT", "The current assessment does not match exact scope.")
        elif assessment.targeting_state != "SUPPORTED" or assessment.intent_satisfaction_state != "SUPPORTED":
            fail("QUERY_PAGE_INTENT", "Targeting and intent satisfaction are not both supported.")
        if context["human_required"]:
            fail("HUMAN_REVIEW", "Applicable human review remains incomplete.")
        if not context["references"]:
            fail("EVIDENCE_REFERENCES", "No governed referenceable evidence is available.")
        for reason in context["package_errors"]:
            fail("EVIDENCE_SCOPE_RIGHTS", reason)
        return {"eligible": not failures, "failed_gates": failures,
                "investigation_id": str(row.id), "input_fingerprint": context["fingerprint"],
                "evidence_package_ids": [str(value) for value in context["package_ids"]],
                "evidence_reference_ids": context["references"],
                "adjudication_ids": [str(item.id) for item in context["adjudications"]],
                "assessment_id": str(assessment.id) if assessment else None}

    def generate(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID, *, actor: str) -> ContentBrief:
        row = self._investigation(investigation_id, tenant_id, site_id)
        eligibility = self.eligibility(row.id, tenant_id, site_id)
        if not eligibility["eligible"]:
            reasons = "; ".join(item["reason"] for item in eligibility["failed_gates"])
            raise ContentBriefError(f"Content brief eligibility failed: {reasons}")
        existing = self.session.scalar(select(ContentBrief).where(
            ContentBrief.input_fingerprint == eligibility["input_fingerprint"]))
        if existing:
            return existing
        context = self.context(row)
        assessment = context["assessment"]
        assert assessment is not None
        previous = self.session.scalar(select(ContentBrief).where(
            ContentBrief.investigation_id == row.id).order_by(
                ContentBrief.created_at.desc(), ContentBrief.id.desc()))
        references = eligibility["evidence_reference_ids"]
        cited = {"supporting_reference_ids": references, "nature": "EDITORIAL_HYPOTHESIS"}
        conflicts = list(assessment.limitations_json)
        conflicts.extend(item.description for item in context["gaps"]
                         if context["adjudication_by_gap"].get(item.id).conflict_state != "NONE")
        recommendations = {
            "search_intent_and_tasks": [{"text": assessment.interpreted_user_need, **cited}],
            "required_factual_topics": [{"text": "Explain the bounded calculator task and inputs; specialist validation remains required.", **cited}],
            "suggested_sections": [{"text": "Draft a clear task introduction, input guidance, result explanation, caveats, and next steps.", **cited}],
            "questions_to_answer": [{"text": f"What does a person searching for '{row.exact_query}' need to calculate or understand?", **cited}],
            "title_meta": [{"text": "Draft title and description variants that accurately name the calculator task; do not promise outcomes.", **cited}],
            "headings": [{"text": "Draft headings around the observed task, instructions, result interpretation, and caveats.", **cited}],
            "internal_links": [{"text": "Editorially review relevant owned resources before proposing contextual links.", **cited}],
            "structured_data": [{"text": "Assess eligible structured data separately; eligibility does not imply rich-result availability.", **cited}],
            "accessibility_usability": [{"text": "Review labels, instructions, validation, keyboard flow, and result announcements before implementation.", **cited}],
            "measurement": [{"text": "Define impressions, clicks, engagement, completion, and guardrail baselines before any approved implementation.", **cited}],
            "unchanged": [{"text": "Preserve calculator logic and regulated factual claims until product and specialist review authorizes changes.", **cited}],
        }
        self._validate_claims(recommendations)
        brief = ContentBrief(
            tenant_id=tenant_id, site_id=site_id, investigation_id=row.id,
            query_entity_id=row.query_entity_id, page_entity_id=row.candidate_page_entity_id,
            market_definition_id=row.market_definition_id, exact_query=row.exact_query,
            candidate_url=row.normalized_candidate_url, brief_type="IMPROVE_EXISTING_PAGE",
            status="READY_FOR_REVIEW", method_key=METHOD_KEY, method_version=METHOD_VERSION,
            prompt_version=None, llm_run_id=None, previous_brief_id=previous.id if previous else None,
            input_fingerprint=eligibility["input_fingerprint"],
            evidence_package_ids_json=eligibility["evidence_package_ids"],
            evidence_reference_ids_json=references,
            adjudication_ids_json=eligibility["adjudication_ids"], assessment_id=assessment.id,
            human_review_dependencies_json=[{"review": "EDITORIAL", "required": True},
                {"review": "PRODUCT_OR_SPECIALIST", "required": True},
                {"review": "ANALYTICS", "required": True}],
            executive_summary="A governed draft for editorial review; no page change is authorized.",
            interpreted_user_need=assessment.interpreted_user_need,
            current_page_role=f"Governed assessment: association={assessment.association_state}, targeting={assessment.targeting_state}, intent={assessment.intent_satisfaction_state}.",
            recommended_page_role="Editorial hypothesis: clearly support the exact calculator task while preserving unvalidated product behavior.",
            audience_json=["People researching the exact governed query in the defined market"],
            recommendations_json=recommendations,
            out_of_scope_json=["Production edits", "Calculator logic changes", "Ranking guarantees", "Publication"],
            prohibited_claims_json=list(PROHIBITED), assumptions_json=assessment.assumptions_json,
            conflicts_json=sorted(set(conflicts)), limitations_json=assessment.limitations_json,
            remaining_gaps_json=[item for adjudication in context["adjudications"]
                                 for item in adjudication.remaining_requirements_json],
            recommended_next_action="Review each bounded proposal; approval does not implement it.")
        self.session.add(brief)
        self.session.flush()
        self._create_proposals(brief, references, context["fingerprint"])
        if previous:
            for proposal in self.proposals(previous.id, tenant_id, site_id):
                if proposal.status not in {"REJECTED", "WITHDRAWN", "SUPERSEDED"}:
                    proposal.status = "SUPERSEDED"
        self.investigations._apply_derived(row, context, actor, "CONTENT_BRIEF_GENERATED",
            f"Generated immutable content brief {brief.id}; no implementation occurred.")
        return brief

    def _create_proposals(self, brief: ContentBrief, references: list[str], fingerprint: str) -> None:
        specs = [
            ("CONTENT_STRUCTURE", "page structure", "Draft an editorial structure covering task, inputs, results, caveats, and next steps.", "EDITORIAL", False, True, False),
            ("ACCESSIBILITY_USABILITY", "calculator instructions and controls", "Review and draft accessible labels, instructions, errors, keyboard flow, and result announcements.", "PRODUCT", True, True, False),
            ("MEASUREMENT", "analytics instrumentation", "Specify measurement events and baselines before any approved content implementation.", "ANALYTICS", True, False, True),
        ]
        previous = self.session.scalars(select(PageChangeProposal).where(
            PageChangeProposal.investigation_id == brief.investigation_id).order_by(
                PageChangeProposal.created_at.desc(), PageChangeProposal.id.desc())).all()
        previous_by_category = {item.category: item for item in previous}
        for category, region, instruction, owner, engineering, compliance, analytics in specs:
            identity = _digest([brief.id, category, region, instruction, references])
            self.session.add(PageChangeProposal(content_brief_id=brief.id,
                investigation_id=brief.investigation_id, target_page=brief.candidate_url,
                category=category, target_region=region,
                current_observed_state="No unrestricted current-state claim is made; verify against governed owned-page observations.",
                proposed_instruction=instruction,
                rationale="Editorial hypothesis grounded in the governed investigation and requiring human review.",
                supporting_reference_ids_json=references, conflicting_reference_ids_json=[],
                expected_qualitative_effect="Hypothesis: improve clarity and task support; impact requires measurement.",
                measurement_signal="Predefine scoped observation and guardrail metrics before implementation.",
                risk="Draft may be inappropriate without editorial, product, compliance, and evidence review.",
                dependencies_json=["Human review", "Implementation planning", "Measurement plan"],
                review_requirements_json=["EDITORIAL", "PRODUCT", "ANALYTICS"],
                implementation_owner_type=owner, engineering_required=engineering,
                compliance_review_required=compliance,
                analytics_instrumentation_required=analytics, status="READY_FOR_REVIEW",
                previous_proposal_id=(previous_by_category[category].id
                    if category in previous_by_category else None), identity_hash=identity,
                evidence_fingerprint=fingerprint))

    def _validate_claims(self, value: object) -> None:
        text = json.dumps(value).casefold()
        for phrase in PROHIBITED:
            if phrase in text:
                raise ContentBriefError(f"Unsupported claim boundary violated: {phrase}")

    def scoped_brief(self, brief_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> ContentBrief:
        brief = self.session.get(ContentBrief, brief_id)
        if not brief or brief.tenant_id != tenant_id or brief.site_id != site_id:
            raise ContentBriefError("Content brief not found in tenant/site scope.")
        return brief

    def briefs(self, investigation_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> list[ContentBrief]:
        self._investigation(investigation_id, tenant_id, site_id)
        return list(self.session.scalars(select(ContentBrief).where(
            ContentBrief.investigation_id == investigation_id,
            ContentBrief.tenant_id == tenant_id, ContentBrief.site_id == site_id).order_by(
                ContentBrief.created_at.desc(), ContentBrief.id.desc())))

    def proposals(self, brief_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> list[PageChangeProposal]:
        self.scoped_brief(brief_id, tenant_id, site_id)
        return list(self.session.scalars(select(PageChangeProposal).where(
            PageChangeProposal.content_brief_id == brief_id).order_by(
                PageChangeProposal.created_at, PageChangeProposal.id)))

    def scoped_proposal(self, proposal_id: uuid.UUID, tenant_id: uuid.UUID,
        site_id: uuid.UUID) -> PageChangeProposal:
        proposal = self.session.get(PageChangeProposal, proposal_id)
        if not proposal:
            raise ContentBriefError("Page-change proposal was not found.")
        self.scoped_brief(proposal.content_brief_id, tenant_id, site_id)
        return proposal

    def review(self, proposal_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        *, reviewer: str, decision: str, comment: str | None) -> ContentProposalReview:
        if not reviewer.strip() or decision not in DECISIONS:
            raise ContentBriefError("A valid reviewer and review decision are required.")
        proposal = self.scoped_proposal(proposal_id, tenant_id, site_id)
        brief = self.scoped_brief(proposal.content_brief_id, tenant_id, site_id)
        current = self.context(self._investigation(brief.investigation_id, tenant_id, site_id))
        if current["fingerprint"] != proposal.evidence_fingerprint:
            proposal.status = "NEEDS_MORE_EVIDENCE"
            raise StaleProposalError("Proposal evidence is materially stale and requires reassessment.")
        status = {"APPROVE": "APPROVED", "REJECT": "REJECTED",
                  "REQUEST_CHANGES": "DRAFT", "NEEDS_MORE_EVIDENCE": "NEEDS_MORE_EVIDENCE"}[decision]
        if proposal.status in {"SUPERSEDED", "WITHDRAWN"}:
            raise ContentBriefError("A superseded or withdrawn proposal cannot be reviewed.")
        review = ContentProposalReview(proposal_id=proposal.id, reviewer=reviewer,
            decision=decision, comment=comment, evidence_fingerprint=proposal.evidence_fingerprint,
            scope_fingerprint=_digest([brief.query_entity_id, brief.page_entity_id,
                                       brief.market_definition_id, brief.exact_query,
                                       brief.candidate_url]), reviewed_at=_now())
        self.session.add(review)
        proposal.status = status
        return review

    def transition(self, proposal_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID,
        action: str) -> PageChangeProposal:
        proposal = self.scoped_proposal(proposal_id, tenant_id, site_id)
        if action == "WITHDRAW" and proposal.status not in {"SUPERSEDED", "WITHDRAWN"}:
            proposal.status = "WITHDRAWN"
        elif action == "SUPERSEDE" and proposal.status != "WITHDRAWN":
            proposal.status = "SUPERSEDED"
        elif action == "MARK_READY_FOR_MEASUREMENT_PLANNING" and proposal.status == "APPROVED":
            proposal.status = "READY_FOR_MEASUREMENT_PLANNING"
        else:
            raise ContentBriefError("Invalid page-change proposal transition.")
        return proposal

    def brief_model(self, brief: ContentBrief) -> dict[str, Any]:
        proposals = self.proposals(brief.id, brief.tenant_id, brief.site_id)
        return {"id": str(brief.id), "investigation_id": str(brief.investigation_id),
            "status": brief.status, "brief_type": brief.brief_type,
            "summary": brief.executive_summary, "exact_query": brief.exact_query,
            "candidate_url": brief.candidate_url, "market_id": str(brief.market_definition_id),
            "user_need": brief.interpreted_user_need, "current_page_role": brief.current_page_role,
            "recommended_page_role": brief.recommended_page_role,
            "recommendations": brief.recommendations_json,
            "out_of_scope": brief.out_of_scope_json, "prohibited_claims": brief.prohibited_claims_json,
            "assumptions": brief.assumptions_json, "conflicts": brief.conflicts_json,
            "limitations": brief.limitations_json, "remaining_gaps": brief.remaining_gaps_json,
            "next_action": brief.recommended_next_action,
            "review_dependencies": brief.human_review_dependencies_json,
            "proposals": [self.proposal_model(item) for item in proposals],
            "technical": {"input_fingerprint": brief.input_fingerprint,
                "method": f"{brief.method_key}:{brief.method_version}",
                "previous_brief_id": str(brief.previous_brief_id) if brief.previous_brief_id else None,
                "evidence_package_ids": brief.evidence_package_ids_json,
                "evidence_reference_ids": brief.evidence_reference_ids_json,
                "adjudication_ids": brief.adjudication_ids_json,
                "assessment_id": str(brief.assessment_id), "llm_run_id": None}}

    def proposal_model(self, proposal: PageChangeProposal) -> dict[str, Any]:
        reviews = list(self.session.scalars(select(ContentProposalReview).where(
            ContentProposalReview.proposal_id == proposal.id).order_by(
                ContentProposalReview.reviewed_at, ContentProposalReview.id)))
        return {"id": str(proposal.id), "brief_id": str(proposal.content_brief_id),
            "status": proposal.status, "category": proposal.category,
            "target_page": proposal.target_page, "target_region": proposal.target_region,
            "current_observed_state": proposal.current_observed_state,
            "proposed_instruction": proposal.proposed_instruction, "rationale": proposal.rationale,
            "supporting_reference_ids": proposal.supporting_reference_ids_json,
            "conflicting_reference_ids": proposal.conflicting_reference_ids_json,
            "expected_qualitative_effect": proposal.expected_qualitative_effect,
            "measurement_signal": proposal.measurement_signal, "risk": proposal.risk,
            "dependencies": proposal.dependencies_json,
            "review_requirements": proposal.review_requirements_json,
            "engineering_required": proposal.engineering_required,
            "compliance_review_required": proposal.compliance_review_required,
            "analytics_instrumentation_required": proposal.analytics_instrumentation_required,
            "reviews": [{"reviewer": item.reviewer, "decision": item.decision,
                         "comment": item.comment, "reviewed_at": item.reviewed_at.isoformat()}
                        for item in reviews]}
