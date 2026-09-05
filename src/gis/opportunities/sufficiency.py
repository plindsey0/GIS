from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gis.models import (
    AnalyticalEntity,
    CollectionPlanningDecision,
    CollectionPlanningRun,
    CollectionTarget,
    CollectionTargetEvidence,
    CollectionTargetStatus,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    Opportunity,
    RightsUsability,
)
from gis.opportunities.market_resolution import resolve_portfolio, resolve_query
from gis.opportunities.service import DETECTORS, VERSION

METHOD_VERSION = "OPPORTUNITY_SUFFICIENCY_V1"


def _condition(
    key: str,
    label: str,
    passed: bool,
    required: Any,
    observed: Any,
    remediation: str,
    action: str,
    *,
    hard_gate: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "passed": passed,
        "hard_gate": hard_gate,
        "required": required,
        "observed": observed,
        "remediation": None if passed else remediation,
        "next_action": None if passed else action,
    }


def detector_inventory() -> dict[str, Any]:
    items = []
    for key, spec in DETECTORS.items():
        items.append(
            {
                "key": key,
                "name": spec["name"],
                "version": VERSION,
                "family": spec["family"].value,
                "enabled": spec["enabled"],
                "experimental": False,
                "evidence_contract": spec["contract"],
                "eligible_classifications": spec["classifications"],
                "activation_sufficiency": spec["activation_sufficiency"],
                "watch_sufficiency": spec["watch_sufficiency"],
                "required_context": spec["requires_metadata"],
                "output_lifecycle": (
                    "WATCHING_ONLY" if not spec["activation_sufficiency"] else "ACTIVE_OR_WATCHING"
                ),
                "claim_type": spec["claim_type"],
                "temporal_requirement": spec["temporal_requirement"],
                "history_requirement": (
                    "Multiple temporally separated observations are required."
                    if spec["claim_type"] == "LONGITUDINAL"
                    else "A trustworthy current observation is sufficient; velocity is not claimed."
                ),
                "prohibited_shortcuts": [
                    "No synthetic evidence",
                    "No threshold weakening",
                    "No paid-provider execution",
                ],
            }
        )
    return {"detector_version": VERSION, "method_version": METHOD_VERSION, "items": items}


def _readiness(conditions: list[dict[str, Any]], spec: dict[str, Any]) -> str:
    failures = {item["key"] for item in conditions if item["hard_gate"] and not item["passed"]}
    if not failures:
        return "QUALIFIED"
    if "rights" in failures or "enabled" in failures:
        return "BLOCKED"
    classification = next(item for item in conditions if item["key"] == "classification")
    if "classification" in failures and classification["remediation"] == "WAIT":
        return "WAITING_FOR_HISTORY"
    if "conflicts" in failures:
        return "PROCESSING_REQUIRED"
    if "metadata" in failures:
        return "PROCESSING_REQUIRED"
    if failures == {"sufficiency"}:
        return "COLLECTION_REQUIRED"
    passed = sum(item["passed"] for item in conditions if item["hard_gate"])
    total = sum(item["hard_gate"] for item in conditions)
    return "NEAR_QUALIFIED" if total - passed == 1 else "NOT_READY"


def diagnose(session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
    rows = session.execute(
        select(EvidencePackage, AnalyticalEntity)
        .join(AnalyticalEntity)
        .where(EvidencePackage.tenant_id == tenant_id, EvidencePackage.site_id == site_id)
        .order_by(EvidencePackage.created_at.desc(), EvidencePackage.id)
    ).all()
    items: list[dict[str, Any]] = []
    failure_counts: Counter[str] = Counter()
    remediation_counts: Counter[str] = Counter()
    for package, entity in rows:
        detector_results = []
        for key, spec in DETECTORS.items():
            classification_ok = package.classification in spec["classifications"]
            conditions = [
                _condition(
                    "enabled",
                    "Detector is enabled",
                    bool(spec["enabled"]),
                    True,
                    spec["enabled"],
                    "BLOCKED",
                    "Enable the reviewed detector policy.",
                ),
                _condition(
                    "classification",
                    "Observed history produces an eligible classification",
                    classification_ok,
                    spec["classifications"],
                    package.classification,
                    "WAIT" if package.classification == "FIRST_OBSERVED" else "THRESHOLD_NOT_MET",
                    "Allow additional real observations to establish velocity; rerun deterministic demand and evidence processing.",
                ),
                _condition(
                    "rights",
                    "Evidence rights are usable",
                    package.rights_usability is RightsUsability.USABLE,
                    "USABLE",
                    package.rights_usability.value,
                    "RIGHTS_BLOCKED",
                    "Complete the governing rights review; UNKNOWN is not permission.",
                ),
                _condition(
                    "conflicts",
                    "No unresolved evidence conflicts",
                    package.conflict_count == 0,
                    0,
                    package.conflict_count,
                    "RESOLVE",
                    "Resolve contradictory evidence or wait for a defensible adjudication.",
                ),
                _condition(
                    "metadata",
                    "Required entity context is present",
                    all(
                        entity.metadata_json.get(name) == expected
                        for name, expected in spec["requires_metadata"].items()
                    ),
                    spec["requires_metadata"],
                    {name: entity.metadata_json.get(name) for name in spec["requires_metadata"]},
                    (
                        "RESOLVE_COVERAGE"
                        if "coverage_state" in spec["requires_metadata"]
                        else "RESOLVE_METADATA"
                    ),
                    (
                        "Establish a governed asset-to-concept coverage assertion; waiting alone cannot resolve this."
                        if "coverage_state" in spec["requires_metadata"]
                        else "Resolve the required deterministic entity metadata; waiting alone cannot resolve this."
                    ),
                ),
                _condition(
                    "sufficiency",
                    "Evidence reaches an activation or watch sufficiency",
                    package.sufficiency.value
                    in [*spec["activation_sufficiency"], *spec["watch_sufficiency"]],
                    [*spec["activation_sufficiency"], *spec["watch_sufficiency"]],
                    package.sufficiency.value,
                    "COLLECT",
                    "Collect the missing rights-permitted evidence identified by the package gaps, then rebuild evidence.",
                ),
            ]
            readiness = _readiness(conditions, spec)
            output_status = (
                "ACTIVE"
                if package.sufficiency.value in spec["activation_sufficiency"]
                else "WATCHING"
            )
            for condition in conditions:
                if not condition["passed"]:
                    failure_counts[condition["key"]] += 1
                    remediation_counts[condition["remediation"]] += 1
            detector_results.append(
                {
                    "detector_key": key,
                    "detector_name": spec["name"],
                    "readiness": readiness,
                    "qualifies": readiness == "QUALIFIED",
                    "output_status": output_status if readiness == "QUALIFIED" else None,
                    "conditions_passed": sum(condition["passed"] for condition in conditions),
                    "conditions_total": len(conditions),
                    "conditions": conditions,
                }
            )
        closest = sorted(
            detector_results,
            key=lambda row: (row["qualifies"], row["conditions_passed"], row["detector_key"]),
            reverse=True,
        )[0]
        items.append(
            {
                "evidence_package_id": str(package.id),
                "label": entity.display_name,
                "entity_type": entity.entity_type.value,
                "entity_key": entity.canonical_key,
                "classification": package.classification,
                "sufficiency": package.sufficiency.value,
                "rights": package.rights_usability.value,
                "conflict_count": package.conflict_count,
                "source_count": package.independent_source_count,
                "market_concept": resolve_query(entity.display_name),
                "period_start": package.period_start.isoformat(),
                "period_end": package.period_end.isoformat(),
                "qualifies": any(row["qualifies"] for row in detector_results),
                "closest": closest,
                "detectors": detector_results,
                "href": f"/opportunities/candidates/{package.id}?detector={closest['detector_key']}",
                "evidence_href": f"/evidence/{package.id}",
            }
        )
    rank = {
        "QUALIFIED": 6,
        "NEAR_QUALIFIED": 5,
        "COLLECTION_REQUIRED": 4,
        "PROCESSING_REQUIRED": 3,
        "WAITING_FOR_HISTORY": 2,
        "NOT_READY": 1,
        "BLOCKED": 0,
    }
    near = sorted(
        items,
        key=lambda row: (
            rank[row["closest"]["readiness"]],
            row["closest"]["conditions_passed"],
            row["label"],
        ),
        reverse=True,
    )
    qualified = sum(row["qualifies"] for row in items)
    return {
        "detector_version": VERSION,
        "method_version": METHOD_VERSION,
        "evaluated": len(items),
        "qualified": qualified,
        "not_qualified": len(items) - qualified,
        "persisted_evaluation_count": session.scalar(select(func.count()).select_from(Opportunity))
        or 0,
        "diagnostics_persisted_for_nonqualifiers": False,
        "diagnostics_materialization": "DERIVED_READ_MODEL",
        "failure_counts": [
            {"condition": key, "count": count} for key, count in failure_counts.most_common()
        ],
        "remediation_counts": [
            {"remediation": key, "count": count} for key, count in remediation_counts.most_common()
        ],
        "reason_counts": [
            {"reason": key.replace("_", " ").title(), "count": count}
            for key, count in failure_counts.most_common()
        ],
        "near_misses": near[:10],
        "items": items,
        "semantics": "Read-only diagnostics apply every published hard gate to every governed evidence package. A count is context, never a substitute for a failed gate.",
    }


def candidate(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    package_id: uuid.UUID,
    detector_key: str | None = None,
) -> dict[str, Any]:
    report = diagnose(session, tenant_id, site_id)
    item = next(
        (row for row in report["items"] if row["evidence_package_id"] == str(package_id)), None
    )
    if not item:
        raise ValueError("candidate evidence package not found in site scope")
    detector = next(
        (row for row in item["detectors"] if row["detector_key"] == detector_key), item["closest"]
    )
    gaps = list(
        session.scalars(
            select(EvidenceGap).where(
                EvidenceGap.evidence_package_id == package_id, EvidenceGap.resolved_at.is_(None)
            )
        )
    )
    evidence = list(
        session.scalars(
            select(EvidencePackageItem).where(EvidencePackageItem.evidence_package_id == package_id)
        )
    )
    return {
        **item,
        "selected_detector": detector,
        "open_gaps": [
            {
                "id": str(gap.id),
                "type": gap.gap_type,
                "description": gap.description,
                "desired_capability": gap.desired_evidence_capability,
                "target_id": str(gap.collection_target_id) if gap.collection_target_id else None,
                "href": f"/evidence/gaps/{gap.id}",
            }
            for gap in gaps
        ],
        "evidence_items": [
            {
                "type": row.evidence_type,
                "role": row.evidence_role,
                "source": row.root_source_key,
                "supports_claim": row.supports_claim,
                "rights": row.rights_usability.value,
            }
            for row in evidence
        ],
        "recommendation_context": {
            "state": "READY_FOR_RECOMMENDATION"
            if detector["qualifies"] and detector["output_status"] == "ACTIVE"
            else "NOT_READY",
            "llm_invoked": False,
            "rights_safe": item["rights"] == "USABLE",
            "evidence_package_ids": [str(package_id)],
            "detector_key": detector["detector_key"],
            "limitations": [
                condition["next_action"]
                for condition in detector["conditions"]
                if not condition["passed"]
            ],
        },
        "opportunity_package": {
            "opportunity_id": None,
            "opportunity_class": detector["detector_key"],
            "market_concept": item["market_concept"],
            "deterministic_claim": detector["detector_name"],
            "detector": {"key": detector["detector_key"], "version": VERSION},
            "supporting_evidence": [row.evidence_key for row in evidence],
            "evidence_provenance": [
                {
                    "source": row.root_source_key,
                    "reference_id": str(row.evidence_reference_id)
                    if row.evidence_reference_id
                    else None,
                    "rights": row.rights_usability.value,
                }
                for row in evidence
            ],
            "market_state": {
                "demand": {
                    "classification": item["classification"],
                    "sufficiency": item["sufficiency"],
                },
                "coverage": item["market_concept"].get("coverage_state", "UNKNOWN"),
                "competition": "UNKNOWN",
                "temporal": detector["detector_key"]
                in {
                    "EMERGING_DEMAND_VISIBILITY_GAP",
                    "DEMAND_ACCELERATION_GAP",
                    "HIGH_VALUE_EVIDENCE_GAP",
                },
            },
            "important_unknowns": [
                condition["label"]
                for condition in detector["conditions"]
                if not condition["passed"]
            ],
            "rights_constraints": item["rights"],
            "permitted_downstream_uses": ["GOVERNED_RECOMMENDATION_CONTEXT"]
            if item["rights"] == "USABLE"
            else [],
            "external_dispatch_allowed": False,
        },
    }


def _latest_decisions(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[uuid.UUID, CollectionPlanningDecision]:
    latest = session.scalar(
        select(CollectionPlanningRun)
        .where(
            CollectionPlanningRun.tenant_id == tenant_id, CollectionPlanningRun.site_id == site_id
        )
        .order_by(CollectionPlanningRun.evaluated_at.desc())
    )
    if not latest:
        return {}
    return {
        row.target_id: row
        for row in session.scalars(
            select(CollectionPlanningDecision).where(
                CollectionPlanningDecision.planning_run_id == latest.id
            )
        )
    }


def portfolio(session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
    targets = list(
        session.scalars(
            select(CollectionTarget)
            .where(CollectionTarget.tenant_id == tenant_id, CollectionTarget.site_id == site_id)
            .order_by(CollectionTarget.target_type, CollectionTarget.display_value)
        )
    )
    decisions = _latest_decisions(session, tenant_id, site_id)
    evidence_counts: dict[uuid.UUID, int] = (
        {
            target_id: count
            for target_id, count in session.execute(
                select(CollectionTargetEvidence.target_id, func.count())
                .where(CollectionTargetEvidence.target_id.in_([row.id for row in targets]))
                .group_by(CollectionTargetEvidence.target_id)
            ).all()
        }
        if targets
        else {}
    )
    items = []
    tiers: Counter[str] = Counter()
    for target in targets:
        decision = decisions.get(target.id)
        if target.status is CollectionTargetStatus.ACTIVE:
            tier = "ACTIVE"
        elif decision and decision.priority_tier.value in {"CRITICAL", "HIGH"}:
            tier = "STRATEGIC"
        elif target.status is CollectionTargetStatus.CANDIDATE:
            tier = "DISCOVERY"
        else:
            tier = "WATCHLIST"
        tiers[tier] += 1
        items.append(
            {
                "id": str(target.id),
                "label": target.display_value,
                "target_type": target.target_type.value,
                "lifecycle": target.status.value,
                "portfolio_tier": tier,
                "authorized": target.status is CollectionTargetStatus.ACTIVE,
                "evidence_count": evidence_counts.get(target.id, 0),
                "priority_score": float(decision.priority_score) if decision else None,
                "priority_tier": decision.priority_tier.value if decision else None,
                "cadence": decision.effective_cadence.value if decision else None,
                "blocker": decision.primary_blocker.value if decision else "NO_PLAN",
                "href": f"/collection/{target.id}",
            }
        )
    return {
        "method_version": METHOD_VERSION,
        "total": len(items),
        "tier_counts": dict(tiers),
        "items": items,
        "semantics": "Portfolio tiers are read-only interpretations of existing target lifecycle and latest planning decisions. They do not authorize, activate, schedule, or collect a target.",
    }


def collection_plan(session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
    diagnostics = diagnose(session, tenant_id, site_id)
    portfolio_data = portfolio(session, tenant_id, site_id)
    target_by_label = {row["label"].casefold(): row for row in portfolio_data["items"]}
    actions = []
    for item in diagnostics["near_misses"]:
        failed = [
            condition for condition in item["closest"]["conditions"] if not condition["passed"]
        ]
        target = target_by_label.get(item["label"].casefold()) or target_by_label.get(
            item["entity_key"].casefold()
        )
        for condition in failed:
            actions.append(
                {
                    "candidate_id": item["evidence_package_id"],
                    "candidate": item["label"],
                    "detector_key": item["closest"]["detector_key"],
                    "readiness": item["closest"]["readiness"],
                    "remediation": condition["remediation"],
                    "action": condition["next_action"],
                    "target": target,
                    "requires_operator_approval": condition["remediation"]
                    in {"COLLECT", "EXPAND_TARGETS", "ENABLE_SOURCE", "AUTHORIZE_TARGET"},
                    "provider_call": False,
                    "estimated_cost": None,
                    "time_to_sufficiency": None,
                    "waiting_can_help": condition["remediation"] == "WAIT",
                    "opportunity_classes_helped": [item["closest"]["detector_key"]],
                    "evidence_gap_addressed": condition["key"],
                    "incremental_requests": 0 if condition["remediation"] == "WAIT" else None,
                    "expected_information_gain": "ONE_BLOCKING_GATE"
                    if len(failed) == 1
                    else "PARTIAL",
                }
            )
    leverage = Counter((row["remediation"], row["action"]) for row in actions)
    return {
        "method_version": METHOD_VERSION,
        "actions": actions,
        "collection_leverage": [
            {"remediation": key[0], "action": key[1], "candidates_helped": count}
            for key, count in leverage.most_common()
        ],
        "budget_scenarios": [
            {
                "name": "NO_NEW_SPEND",
                "description": "Wait for already-authorized collection and run deterministic downstream processing.",
                "cost": 0,
            },
            {
                "name": "REVIEW_REQUIRED",
                "description": "Any new or paid collection remains unpriced and requires explicit operator authorization.",
                "cost": None,
            },
        ],
        "semantics": "This is a bounded recommendation plan only. It makes zero provider calls and changes no target, schedule, budget, rights policy, or obligation.",
    }


def baseline(session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID) -> dict[str, Any]:
    diagnostics = diagnose(session, tenant_id, site_id)
    plan = collection_plan(session, tenant_id, site_id)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "detectors": detector_inventory(),
        "diagnostics": diagnostics,
        "portfolio": portfolio(session, tenant_id, site_id),
        "market_resolution": resolve_portfolio(session, tenant_id, site_id),
        "bootstrap_readiness": bootstrap_readiness(session, tenant_id, site_id),
        "collection_plan": plan,
        "provider_calls": 0,
        "state_mutations": 0,
    }


def bootstrap_readiness(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    diagnostics = diagnose(session, tenant_id, site_id)
    resolution = resolve_portfolio(session, tenant_id, site_id)
    by_class: Counter[str] = Counter()
    blockers: Counter[str] = Counter()
    waiting = 0
    waiting_never_helps = 0
    for item in diagnostics["items"]:
        by_class[item["closest"]["detector_key"]] += 1
        failed = [c for c in item["closest"]["conditions"] if not c["passed"]]
        for condition in failed:
            blockers[condition["remediation"]] += 1
        if failed and all(c["remediation"] == "WAIT" for c in failed):
            waiting += 1
        elif failed:
            waiting_never_helps += 1
    unsupported = [
        {"class": name, "state": "DEFINED_UNSUPPORTED"}
        for name in (
            "DECLINING_DEMAND",
            "POSITION_LOSS",
            "POSITION_GAIN",
            "COMPETITOR_CHANGE",
            "TECHNOLOGY_CHANGE",
        )
    ]
    return {
        "method_version": METHOD_VERSION,
        "qualified": diagnostics["qualified"],
        "near_qualified_by_class": dict(by_class),
        "canonical_market_concepts_evaluated": resolution["canonical_market_concepts"],
        "concepts_requiring_longitudinal_evidence": sum(
            1 for item in diagnostics["items"] if item["classification"] == "FIRST_OBSERVED"
        ),
        "waiting_for_history": waiting,
        "waiting_will_not_fix": waiting_never_helps,
        "blockers": dict(blockers),
        "unsupported_opportunity_classes": unsupported,
        "highest_leverage_actions": collection_plan(session, tenant_id, site_id)[
            "collection_leverage"
        ][:5],
        "llm_ready": diagnostics["qualified"] > 0,
        "semantics": "Bootstrap readiness is deterministic. WAIT is used only when existing future observations can satisfy the sole blocker.",
    }
