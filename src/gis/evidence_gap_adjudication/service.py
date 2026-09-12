from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from gis.collection_planning.service import normalize_target
from gis.models import (
    CollectionRequirement,
    CollectionRequirementStatus,
    EvidenceCompatibility,
    EvidenceGap,
    EvidenceGapAdjudication,
    EvidenceGapAdjudicationEvidence,
    EvidenceGapAdjudicationReview,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceReassessmentStatus,
    ExactQuerySerpSnapshotDetail,
    OwnedSurfaceObservationDetail,
    QueryPageIntentAssessment,
    QueryPageIntentEvidence,
    RightsUsability,
)

METHOD_KEY = "governed_evidence_gap_adjudication"
METHOD_VERSION = "1.0"


class EvidenceGapAdjudicationError(ValueError):
    pass


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fresh_after(requirement: Optional[CollectionRequirement], evaluated_at: datetime) -> date:
    days = {
        "DAILY": 2,
        "MULTIPLE_PER_WEEK": 7,
        "WEEKLY": 14,
        "MONTHLY": 45,
        "ON_DEMAND": 90,
        "NONE": 90,
    }.get(requirement.freshness_expectation.value if requirement else "ON_DEMAND", 90)
    return (evaluated_at - timedelta(days=days)).date()


class EvidenceGapAdjudicationService:
    """Purely deterministic adjudication over already-persisted governed evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def adjudicate(
        self,
        gap_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        evidence_package_ids: list[uuid.UUID],
        evidence_reference_ids: Optional[list[uuid.UUID]] = None,
        evaluated_at: Optional[datetime] = None,
    ) -> EvidenceGapAdjudication:
        evaluated_at = evaluated_at or _now()
        gap = self.session.get(EvidenceGap, gap_id)
        if not gap:
            raise EvidenceGapAdjudicationError("Evidence gap not found.")
        governing = self.session.get(EvidencePackage, gap.evidence_package_id)
        if not governing or governing.tenant_id != tenant_id or governing.site_id != site_id:
            raise EvidenceGapAdjudicationError("Evidence gap is outside tenant/site scope.")
        requirement = self.session.scalar(
            select(CollectionRequirement)
            .where(
                CollectionRequirement.evidence_gap_id == gap.id,
                CollectionRequirement.tenant_id == tenant_id,
                CollectionRequirement.site_id == site_id,
            )
            .order_by(CollectionRequirement.created_at.desc(), CollectionRequirement.id.desc())
        )
        packages = [
            self.session.get(EvidencePackage, item)
            for item in sorted(set(evidence_package_ids), key=str)
        ]
        if any(package is None for package in packages):
            raise EvidenceGapAdjudicationError("One or more evidence packages do not exist.")
        selected = [package for package in packages if package is not None]
        for package in selected:
            if package.tenant_id != tenant_id or package.site_id != site_id:
                raise EvidenceGapAdjudicationError("Evidence package is outside tenant/site scope.")
            if package.analytical_entity_id != governing.analytical_entity_id:
                raise EvidenceGapAdjudicationError(
                    "Evidence package is outside analytical-entity scope."
                )
            if package.market_definition_id != governing.market_definition_id:
                raise EvidenceGapAdjudicationError("Evidence package is outside market scope.")
        references = sorted(set(evidence_reference_ids or []), key=str)
        evidence_state, allowable_references = self._evidence_state(selected)
        unknown_references = set(references) - allowable_references
        if unknown_references:
            raise EvidenceGapAdjudicationError(
                "Evidence references are not governed by the selected evidence packages: "
                + ", ".join(map(str, sorted(unknown_references, key=str)))
            )
        fingerprint = _digest(
            {
                "gap_id": gap.id,
                "packages": [package.id for package in selected],
                "references": references,
                "evidence_state": evidence_state,
                "required_capability": gap.desired_evidence_capability or gap.gap_type,
                "method_version": METHOD_VERSION,
            }
        )
        existing = self.session.scalar(
            select(EvidenceGapAdjudication).where(
                EvidenceGapAdjudication.input_fingerprint == fingerprint
            )
        )
        if existing:
            return existing

        result = self._evaluate(gap, governing, requirement, selected, evaluated_at)
        previous = self.session.scalar(
            select(EvidenceGapAdjudication)
            .where(
                EvidenceGapAdjudication.evidence_gap_id == gap.id,
                EvidenceGapAdjudication.is_current.is_(True),
            )
            .order_by(
                EvidenceGapAdjudication.evaluated_at.desc(),
                EvidenceGapAdjudication.created_at.desc(),
                EvidenceGapAdjudication.id.desc(),
            )
        )
        if previous:
            previous.is_current = False
        adjudication = EvidenceGapAdjudication(
            tenant_id=tenant_id,
            site_id=site_id,
            evidence_gap_id=gap.id,
            collection_requirement_id=requirement.id if requirement else None,
            analytical_entity_id=governing.analytical_entity_id,
            market_definition_id=governing.market_definition_id,
            previous_adjudication_id=previous.id if previous else None,
            outcome=result["outcome"],
            method_key=METHOD_KEY,
            method_version=METHOD_VERSION,
            evaluated_at=evaluated_at,
            input_fingerprint=fingerprint,
            required_capability=gap.desired_evidence_capability or gap.gap_type,
            observed_capabilities_json=result["observed_capabilities"],
            evidence_reference_ids_json=list(map(str, references)),
            scope_compatibility="COMPATIBLE",
            identity_compatibility="COMPATIBLE",
            freshness_assessment=result["freshness"],
            rights_assessment=result["rights"],
            method_compatibility=result["method"],
            evidence_sufficiency=result["sufficiency"],
            conflict_state=result["conflict"],
            reasons_json=result["reasons"],
            rejected_evidence_json=result["rejected"],
            remaining_requirements_json=result["remaining"],
            limitations_json=result["limitations"],
            recommended_next_action=result["next_action"],
            human_review_required=result["human_review_required"],
            downstream_reassessment_eligible=(
                result["outcome"] == "SATISFIED" and not result["human_review_required"]
            ),
            is_current=True,
        )
        self.session.add(adjudication)
        self.session.flush()
        self.session.add_all(
            [
                EvidenceGapAdjudicationEvidence(
                    adjudication_id=adjudication.id, evidence_package_id=package.id
                )
                for package in selected
            ]
        )
        if adjudication.outcome == "SATISFIED":
            gap.resolved_at = evaluated_at
            if requirement:
                requirement.status = CollectionRequirementStatus.SATISFIED
                requirement.reassessment_status = EvidenceReassessmentStatus.SATISFIED
                requirement.reassessed_at = evaluated_at
                requirement.satisfying_evidence_package_id = selected[0].id if selected else None
                requirement.reassessment_notes = "Satisfied by governed evidence-gap adjudication."
                if adjudication.downstream_reassessment_eligible:
                    requirement.intelligence_reassessment_eligible_at = evaluated_at
        else:
            gap.resolved_at = None
            if requirement:
                requirement.reassessed_at = evaluated_at
                requirement.reassessment_status = (
                    EvidenceReassessmentStatus.INCONCLUSIVE
                    if adjudication.outcome == "CONFLICTING_EVIDENCE"
                    else EvidenceReassessmentStatus.STILL_INSUFFICIENT
                )
                requirement.reassessment_notes = adjudication.recommended_next_action
                requirement.intelligence_reassessment_eligible_at = None
        return adjudication

    def _evidence_state(
        self, packages: list[EvidencePackage]
    ) -> tuple[dict[str, Any], set[uuid.UUID]]:
        """Return normalized immutable input state and its governed reference allow-list."""
        package_ids = [row.id for row in packages]
        items = (
            list(
                self.session.scalars(
                    select(EvidencePackageItem)
                    .where(EvidencePackageItem.evidence_package_id.in_(package_ids))
                    .order_by(
                        EvidencePackageItem.evidence_package_id,
                        EvidencePackageItem.evidence_key,
                        EvidencePackageItem.id,
                    )
                )
            )
            if package_ids
            else []
        )
        owned = (
            list(
                self.session.scalars(
                    select(OwnedSurfaceObservationDetail)
                    .where(OwnedSurfaceObservationDetail.evidence_package_id.in_(package_ids))
                    .order_by(OwnedSurfaceObservationDetail.observation_id)
                )
            )
            if package_ids
            else []
        )
        serp = (
            list(
                self.session.scalars(
                    select(ExactQuerySerpSnapshotDetail)
                    .where(ExactQuerySerpSnapshotDetail.evidence_package_id.in_(package_ids))
                    .order_by(ExactQuerySerpSnapshotDetail.observation_id)
                )
            )
            if package_ids
            else []
        )
        qpi = (
            list(
                self.session.scalars(
                    select(QueryPageIntentAssessment)
                    .join(
                        QueryPageIntentEvidence,
                        QueryPageIntentEvidence.assessment_id == QueryPageIntentAssessment.id,
                    )
                    .where(
                        QueryPageIntentEvidence.evidence_package_id.in_(package_ids),
                        QueryPageIntentAssessment.is_current.is_(True),
                    )
                    .order_by(QueryPageIntentAssessment.id)
                )
            )
            if package_ids
            else []
        )
        allowable = set(package_ids)
        allowable.update(row.id for row in items)
        allowable.update(row.evidence_reference_id for row in items if row.evidence_reference_id)
        allowable.update(row.observation_id for row in owned)
        allowable.update(row.observation_id for row in serp)
        allowable.update(row.id for row in qpi)
        state = {
            "packages": [
                {
                    "id": row.id,
                    "period_start": row.period_start,
                    "period_end": row.period_end,
                    "rights": row.rights_usability,
                    "sufficiency": row.sufficiency,
                    "conflict_count": row.conflict_count,
                    "limitations": row.limitations_json,
                    "method_version": row.method_version,
                }
                for row in packages
            ],
            "items": [
                {
                    "id": row.id,
                    "reference_id": row.evidence_reference_id,
                    "type": row.evidence_type,
                    "supports_claim": row.supports_claim,
                    "scope": row.scope_compatibility,
                    "method": row.method_compatibility,
                    "rights": row.rights_usability,
                    "metadata": row.metadata_json,
                }
                for row in items
            ],
            "owned": [
                (row.observation_id, row.quality_state, row.reassessment_ready) for row in owned
            ],
            "serp": [
                (row.observation_id, row.quality_state, row.reassessment_ready, row.returned_depth)
                for row in serp
            ],
            "query_page_intent": [
                (
                    row.id,
                    row.input_fingerprint,
                    row.association_state,
                    row.targeting_state,
                    row.intent_satisfaction_state,
                )
                for row in qpi
            ],
        }
        return state, allowable

    def _evaluate(
        self,
        gap: EvidenceGap,
        governing: EvidencePackage,
        requirement: Optional[CollectionRequirement],
        packages: list[EvidencePackage],
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        capability = (gap.desired_evidence_capability or gap.gap_type).upper()
        items = (
            list(
                self.session.scalars(
                    select(EvidencePackageItem)
                    .where(
                        EvidencePackageItem.evidence_package_id.in_([row.id for row in packages])
                    )
                    .order_by(
                        EvidencePackageItem.evidence_package_id,
                        EvidencePackageItem.evidence_key,
                        EvidencePackageItem.id,
                    )
                )
            )
            if packages
            else []
        )
        rejected: list[dict[str, str]] = []
        limitations = sorted({value for package in packages for value in package.limitations_json})
        hard_rights = any(
            package.rights_usability
            not in {RightsUsability.USABLE, RightsUsability.PARTIALLY_USABLE}
            for package in packages
        )
        incompatible = [
            item
            for item in items
            if (
                item.scope_compatibility is not EvidenceCompatibility.COMPATIBLE
                or item.method_compatibility is not EvidenceCompatibility.COMPATIBLE
                or item.rights_usability
                not in {RightsUsability.USABLE, RightsUsability.PARTIALLY_USABLE}
            )
        ]
        for item in incompatible:
            rejected.append({"evidence_id": str(item.id), "reason": "RIGHTS_OR_COMPATIBILITY"})
        fresh_after = _fresh_after(requirement, evaluated_at)
        stale = bool(packages) and all(package.period_end < fresh_after for package in packages)
        conflicts = sum(package.conflict_count for package in packages) > 0
        observed: set[str] = set()
        relevant = False
        ready = False
        quality_limited = False
        semantic_review = False

        def item_matches_requirement(item: EvidencePackageItem) -> bool:
            if not requirement:
                return item.supports_claim is True
            metadata = item.metadata_json or {}
            observed = str(
                metadata.get("url")
                or metadata.get("canonical_url")
                or metadata.get("query")
                or metadata.get("keyword")
                or ""
            )
            try:
                normalized_observed, _ = normalize_target(requirement.target_type, observed)
            except ValueError:
                return False
            if normalized_observed != requirement.normalized_target:
                return False
            if requirement.target_type.value == "QUERY":
                return (
                    metadata.get("country_code") == requirement.country_code
                    and metadata.get("language_code") == requirement.language_code
                    and metadata.get("device") == requirement.device
                )
            return True

        compatible_items = [
            item for item in items if item not in incompatible and item_matches_requirement(item)
        ]

        owned = (
            list(
                self.session.scalars(
                    select(OwnedSurfaceObservationDetail)
                    .where(
                        OwnedSurfaceObservationDetail.evidence_package_id.in_(
                            [row.id for row in packages]
                        )
                    )
                    .order_by(
                        OwnedSurfaceObservationDetail.observed_at.desc(),
                        OwnedSurfaceObservationDetail.observation_id.desc(),
                    )
                )
            )
            if packages
            else []
        )
        serp = (
            list(
                self.session.scalars(
                    select(ExactQuerySerpSnapshotDetail)
                    .where(
                        ExactQuerySerpSnapshotDetail.evidence_package_id.in_(
                            [row.id for row in packages]
                        )
                    )
                    .order_by(
                        ExactQuerySerpSnapshotDetail.observed_at.desc(),
                        ExactQuerySerpSnapshotDetail.observation_id.desc(),
                    )
                )
            )
            if packages
            else []
        )
        qpi = (
            list(
                self.session.scalars(
                    select(QueryPageIntentAssessment)
                    .join(
                        QueryPageIntentEvidence,
                        QueryPageIntentEvidence.assessment_id == QueryPageIntentAssessment.id,
                    )
                    .where(
                        QueryPageIntentEvidence.evidence_package_id.in_(
                            [row.id for row in packages]
                        ),
                        QueryPageIntentAssessment.is_current.is_(True),
                    )
                    .order_by(
                        QueryPageIntentAssessment.evaluated_at.desc(),
                        QueryPageIntentAssessment.id.desc(),
                    )
                )
            )
            if packages
            else []
        )
        target_id = requirement.collection_target_id if requirement else gap.collection_target_id
        if target_id:
            owned = [row for row in owned if row.collection_target_id == target_id]
            serp = [
                row
                for row in serp
                if row.collection_target_id == target_id
                and row.market_definition_id == governing.market_definition_id
            ]
        qpi = [
            row
            for row in qpi
            if row.tenant_id == governing.tenant_id
            and row.site_id == governing.site_id
            and row.query_entity_id == governing.analytical_entity_id
            and row.market_definition_id == governing.market_definition_id
        ]
        if requirement:
            qpi = [
                row
                for row in qpi
                if row.query_entity_id == governing.analytical_entity_id
                and (
                    requirement.target_type.value != "URL"
                    or row.page_url.rstrip("/").casefold()
                    == requirement.normalized_target.rstrip("/").casefold()
                )
            ]
        if owned:
            observed.add("OWNED_PAGE_CONTENT")
        if serp:
            observed.add("EXACT_QUERY_SERP")
        if qpi:
            observed.add("QUERY_PAGE_INTENT")

        if "OWNED" in capability or "PAGE_CONTENT" in capability:
            legacy = [
                item
                for item in compatible_items
                if any(
                    token in f"{item.evidence_type} {item.root_source_key or ''}".upper()
                    for token in {"CONTENT", "PAGE"}
                )
            ]
            relevant = bool(owned or legacy)
            ready = bool(
                (owned and owned[0].reassessment_ready)
                or any(item.supports_claim is True for item in legacy)
            )
            quality_limited = bool(owned and owned[0].quality_state != "USABLE")
        elif "SERP" in capability:
            legacy = [
                item
                for item in compatible_items
                if "SERP" in (f"{item.evidence_type} {item.root_source_key or ''}".upper())
            ]
            relevant = bool(serp or legacy)
            ready = bool(
                (serp and serp[0].reassessment_ready and serp[0].returned_depth > 0)
                or any(item.supports_claim is True for item in legacy)
            )
            quality_limited = bool(serp and serp[0].quality_state != "USABLE")
        elif "INTENT" in capability or "QUERY_PAGE" in capability:
            relevant = bool(qpi)
            ready = bool(qpi and qpi[0].intent_satisfaction_state == "SUPPORTED")
            conflicts = conflicts or bool(
                qpi
                and (
                    qpi[0].targeting_state == "CONFLICTING_EVIDENCE"
                    or qpi[0].intent_satisfaction_state == "CONFLICTING_EVIDENCE"
                )
            )
            quality_limited = bool(
                qpi
                and qpi[0].intent_satisfaction_state
                in {"PARTIAL", "UNRESOLVED", "INSUFFICIENT_EVIDENCE"}
            )
            semantic_review = True
        else:
            relevant = bool(items)
            ready = any(item.supports_claim is True for item in items)

        supported = bool(packages) and any(
            package.sufficiency.value == "SUPPORTED" for package in packages
        )
        limited = bool(packages) and any(
            package.sufficiency.value == "LIMITED" for package in packages
        )
        if hard_rights or incompatible:
            outcome = "BLOCKED"
        elif conflicts:
            outcome = "CONFLICTING_EVIDENCE"
        elif relevant and ready and supported and not stale and not quality_limited:
            outcome = "SATISFIED"
        elif relevant and (limited or stale or quality_limited or not ready):
            outcome = "PARTIALLY_SATISFIED"
        else:
            outcome = "STILL_INSUFFICIENT"
        remaining = []
        if not relevant:
            remaining.append(f"Collect governed {capability} evidence in exact scope.")
        if stale:
            remaining.append("Collect evidence within the required freshness window.")
        if not supported:
            remaining.append("Obtain evidence with SUPPORTED sufficiency; LIMITED is not promoted.")
        if conflicts:
            remaining.append("Resolve the material governed evidence conflict.")
        reasons = [
            f"Required capability: {capability}.",
            f"Observed capabilities: {', '.join(sorted(observed)) or 'none'}.",
            f"Relevant evidence: {'yes' if relevant else 'no'}; reassessment ready: {'yes' if ready else 'no'}.",
            f"Freshness: {'STALE' if stale else 'CURRENT_OR_UNKNOWN'}; sufficiency: {'SUPPORTED' if supported else 'LIMITED' if limited else 'INSUFFICIENT'}.",
        ]
        next_actions = {
            "SATISFIED": "Reassess downstream intelligence explicitly; do not execute an intervention.",
            "PARTIALLY_SATISFIED": "Address the remaining evidence requirements before reassessment.",
            "STILL_INSUFFICIENT": "Use the existing investigation/collection handoff for the missing capability.",
            "CONFLICTING_EVIDENCE": "Request human review and collect discriminating evidence.",
            "BLOCKED": "Resolve rights or compatibility blockers before using this evidence.",
        }
        return {
            "outcome": outcome,
            "observed_capabilities": sorted(observed),
            "freshness": "STALE" if stale else "CURRENT_OR_UNKNOWN",
            "rights": "BLOCKED" if hard_rights or incompatible else "USABLE",
            "method": "INCOMPATIBLE" if incompatible else "COMPATIBLE",
            "sufficiency": "SUPPORTED" if supported else "LIMITED" if limited else "INSUFFICIENT",
            "conflict": "CONFLICTING" if conflicts else "NONE_OBSERVED",
            "reasons": reasons,
            "rejected": rejected,
            "remaining": remaining,
            "limitations": limitations,
            "next_action": next_actions[outcome],
            "human_review_required": semantic_review
            or outcome in {"CONFLICTING_EVIDENCE", "BLOCKED"},
        }

    def review(
        self,
        adjudication_id: uuid.UUID,
        *,
        tenant_id: uuid.UUID,
        site_id: uuid.UUID,
        decision: Literal["CONFIRM", "DISAGREE", "NEEDS_MORE_EVIDENCE"],
        reviewer: str,
        comment: Optional[str] = None,
        reviewed_at: Optional[datetime] = None,
    ) -> EvidenceGapAdjudicationReview:
        adjudication = self.session.get(EvidenceGapAdjudication, adjudication_id)
        if (
            not adjudication
            or adjudication.tenant_id != tenant_id
            or adjudication.site_id != site_id
        ):
            raise EvidenceGapAdjudicationError("Adjudication not found in tenant/site scope.")
        review = EvidenceGapAdjudicationReview(
            adjudication_id=adjudication.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
            reviewed_at=reviewed_at or _now(),
        )
        self.session.add(review)
        if adjudication.collection_requirement_id and adjudication.human_review_required:
            requirement = self.session.get(
                CollectionRequirement, adjudication.collection_requirement_id
            )
            if requirement:
                requirement.intelligence_reassessment_eligible_at = (
                    review.reviewed_at
                    if decision == "CONFIRM" and adjudication.outcome == "SATISFIED"
                    else None
                )
        return review

    def history(
        self, gap_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
    ) -> list[EvidenceGapAdjudication]:
        return list(
            self.session.scalars(
                select(EvidenceGapAdjudication)
                .where(
                    EvidenceGapAdjudication.evidence_gap_id == gap_id,
                    EvidenceGapAdjudication.tenant_id == tenant_id,
                    EvidenceGapAdjudication.site_id == site_id,
                )
                .order_by(
                    EvidenceGapAdjudication.evaluated_at.desc(),
                    EvidenceGapAdjudication.created_at.desc(),
                    EvidenceGapAdjudication.id.desc(),
                )
            )
        )

    def read_model(self, adjudication: EvidenceGapAdjudication) -> dict[str, Any]:
        return self.read_models([adjudication])[0]

    def read_models(self, adjudications: list[EvidenceGapAdjudication]) -> list[dict[str, Any]]:
        if not adjudications:
            return []
        ids = [row.id for row in adjudications]
        reviews_by_id: dict[uuid.UUID, list[EvidenceGapAdjudicationReview]] = defaultdict(list)
        for review in self.session.scalars(
            select(EvidenceGapAdjudicationReview)
            .where(EvidenceGapAdjudicationReview.adjudication_id.in_(ids))
            .order_by(
                EvidenceGapAdjudicationReview.adjudication_id,
                EvidenceGapAdjudicationReview.reviewed_at,
                EvidenceGapAdjudicationReview.id,
            )
        ):
            reviews_by_id[review.adjudication_id].append(review)
        packages_by_id: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for adjudication_id, package_id in self.session.execute(
            select(
                EvidenceGapAdjudicationEvidence.adjudication_id,
                EvidenceGapAdjudicationEvidence.evidence_package_id,
            )
            .where(EvidenceGapAdjudicationEvidence.adjudication_id.in_(ids))
            .order_by(
                EvidenceGapAdjudicationEvidence.adjudication_id,
                EvidenceGapAdjudicationEvidence.evidence_package_id,
            )
        ):
            packages_by_id[adjudication_id].append(package_id)
        return [
            self._read_model(row, reviews_by_id[row.id], packages_by_id[row.id])
            for row in adjudications
        ]

    @staticmethod
    def _read_model(
        adjudication: EvidenceGapAdjudication,
        reviews: list[EvidenceGapAdjudicationReview],
        packages: list[uuid.UUID],
    ) -> dict[str, Any]:
        latest_review = reviews[-1] if reviews else None
        review_approved = bool(
            latest_review
            and latest_review.decision == "CONFIRM"
            and adjudication.outcome == "SATISFIED"
        )
        return {
            "id": str(adjudication.id),
            "outcome": adjudication.outcome,
            "current_status": adjudication.outcome.replace("_", " ").title(),
            "why": adjudication.reasons_json,
            "evidence_considered": [str(row) for row in packages],
            "evidence_rejected": adjudication.rejected_evidence_json,
            "checks": {
                "scope": adjudication.scope_compatibility,
                "identity": adjudication.identity_compatibility,
                "freshness": adjudication.freshness_assessment,
                "rights": adjudication.rights_assessment,
                "method": adjudication.method_compatibility,
                "sufficiency": adjudication.evidence_sufficiency,
                "conflict": adjudication.conflict_state,
            },
            "remaining_requirements": adjudication.remaining_requirements_json,
            "limitations": adjudication.limitations_json,
            "recommended_next_action": adjudication.recommended_next_action,
            "human_review": {
                "required": adjudication.human_review_required,
                "state": latest_review.decision if latest_review else "UNREVIEWED",
                "history": [
                    {
                        "decision": row.decision,
                        "reviewer": row.reviewer,
                        "comment": row.comment,
                        "reviewed_at": row.reviewed_at.isoformat(),
                    }
                    for row in reviews
                ],
            },
            "reassessment": {
                "eligible": adjudication.downstream_reassessment_eligible or review_approved,
                "gap_closed": adjudication.outcome == "SATISFIED",
            },
            "technical": {
                "gap_id": str(adjudication.evidence_gap_id),
                "collection_requirement_id": str(adjudication.collection_requirement_id)
                if adjudication.collection_requirement_id
                else None,
                "entity_id": str(adjudication.analytical_entity_id),
                "market_id": str(adjudication.market_definition_id)
                if adjudication.market_definition_id
                else None,
                "method": adjudication.method_key,
                "method_version": adjudication.method_version,
                "input_fingerprint": adjudication.input_fingerprint,
                "evidence_reference_ids": adjudication.evidence_reference_ids_json,
                "previous_adjudication_id": str(adjudication.previous_adjudication_id)
                if adjudication.previous_adjudication_id
                else None,
                "evaluated_at": adjudication.evaluated_at.isoformat(),
            },
        }
