from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from gis.api.errors import ApiError
from gis.api.workbench import encoded, row_data
from gis.models import (
    AnalyticalEntity,
    CollectionPlanItem,
    CollectionPlanningDecision,
    CollectionTarget,
    CollectionTargetEvidence,
    CollectorCapability,
    DemandSignal,
    EvidenceContract,
    EvidenceGap,
    EvidencePackage,
    EvidencePackageItem,
    EvidenceQualityDimension,
    MarketDefinition,
    MarketDefinitionMember,
    MarketMetricObservation,
    MarketObservation,
    MarketParticipantObservation,
)
from gis.opportunities.sufficiency import diagnose

COLLECTION_STATUS_HELP = {
    "CANDIDATE": "Discovered and evaluated, but not promoted into an applied collection plan.",
    "ACTIVE": "Included in the current applied collection plan.",
    "DORMANT": "Retained for history but not currently prioritized for collection.",
    "PAUSED": "Collection was deliberately suspended without retiring the target.",
    "REJECTED": "Evaluated and explicitly excluded from collection.",
    "RETIRED": "No longer eligible for routine collection.",
}


def _page(items: list[dict[str, Any]], page: int, limit: int, total: int) -> dict[str, Any]:
    return {"items": items, "page": page, "limit": limit, "total": total}


def evidence_inventory(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    *,
    page: int,
    limit: int,
    search: Optional[str] = None,
    entity_type: Optional[str] = None,
    sufficiency: Optional[str] = None,
    source: Optional[str] = None,
    evidence_type: Optional[str] = None,
    sort: str = "updated",
    order: str = "desc",
) -> dict[str, Any]:
    filters: list[Any] = [
        EvidencePackage.tenant_id == tenant_id,
        EvidencePackage.site_id == site_id,
    ]
    if search:
        filters.append(
            or_(
                AnalyticalEntity.display_name.ilike(f"%{search}%"),
                AnalyticalEntity.canonical_key.ilike(f"%{search}%"),
            )
        )
    if entity_type:
        filters.append(AnalyticalEntity.entity_type == entity_type)
    if sufficiency:
        filters.append(EvidencePackage.sufficiency == sufficiency)
    if source:
        filters.append(
            EvidencePackage.id.in_(
                select(EvidencePackageItem.evidence_package_id).where(
                    EvidencePackageItem.root_source_key == source
                )
            )
        )
    if evidence_type:
        filters.append(
            EvidencePackage.id.in_(
                select(EvidencePackageItem.evidence_package_id).where(
                    EvidencePackageItem.evidence_type == evidence_type
                )
            )
        )
    total = (
        session.scalar(
            select(func.count()).select_from(EvidencePackage).join(AnalyticalEntity).where(*filters)
        )
        or 0
    )
    sort_columns = {
        "name": AnalyticalEntity.display_name,
        "updated": EvidencePackage.created_at,
        "status": EvidencePackage.sufficiency,
        "freshness": EvidencePackage.period_end,
    }
    column = sort_columns.get(sort, EvidencePackage.created_at)
    ordering = desc(column) if order == "desc" else asc(column)
    rows = session.execute(
        select(EvidencePackage, AnalyticalEntity, EvidenceContract)
        .join(AnalyticalEntity)
        .join(EvidenceContract)
        .where(*filters)
        .order_by(ordering, EvidencePackage.id)
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    package_ids = [package.id for package, _, _ in rows]
    sources: dict[uuid.UUID, set[str]] = {package_id: set() for package_id in package_ids}
    for package_id, source_key in session.execute(
        select(EvidencePackageItem.evidence_package_id, EvidencePackageItem.root_source_key).where(
            EvidencePackageItem.evidence_package_id.in_(package_ids)
        )
    ):
        if source_key:
            sources[package_id].add(source_key)
    gap_counts: dict[uuid.UUID, int] = {
        package_id: count
        for package_id, count in session.execute(
            select(EvidenceGap.evidence_package_id, func.count())
            .where(
                EvidenceGap.evidence_package_id.in_(package_ids), EvidenceGap.resolved_at.is_(None)
            )
            .group_by(EvidenceGap.evidence_package_id)
        ).all()
    }
    items = [
        {
            "id": str(package.id),
            "label": entity.display_name,
            "canonical_key": entity.canonical_key,
            "entity_type": entity.entity_type.value,
            "classification": package.classification,
            "evidence_type": contract.contract_key,
            "status": package.sufficiency.value,
            "status_label": f"Evidence {package.sufficiency.value.casefold().replace('_', ' ')}",
            "contract": contract.contract_key,
            "sources": sorted(sources[package.id]),
            "source_count": package.independent_source_count,
            "gap_count": gap_counts.get(package.id, 0),
            "rights": package.rights_usability.value,
            "fresh_through": package.period_end.isoformat(),
            "updated_at": encoded(package.created_at),
            "href": f"/evidence/{package.id}",
        }
        for package, entity, contract in rows
    ]
    return _page(items, page, limit, total)


def opportunity_diagnostics(
    session: Session, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    return diagnose(session, tenant_id, site_id)


def evidence_detail(
    session: Session, package_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    row = session.execute(
        select(EvidencePackage, AnalyticalEntity, EvidenceContract)
        .join(AnalyticalEntity)
        .join(EvidenceContract)
        .where(
            EvidencePackage.id == package_id,
            EvidencePackage.tenant_id == tenant_id,
            EvidencePackage.site_id == site_id,
        )
    ).one_or_none()
    if not row:
        raise ApiError(
            404, "EVIDENCE_PACKAGE_NOT_FOUND", "Evidence package not found in site scope."
        )
    package, entity, contract = row
    dimensions = list(
        session.scalars(
            select(EvidenceQualityDimension).where(
                EvidenceQualityDimension.evidence_package_id == package.id
            )
        )
    )
    items = list(
        session.scalars(
            select(EvidencePackageItem).where(EvidencePackageItem.evidence_package_id == package.id)
        )
    )
    gaps = list(
        session.scalars(select(EvidenceGap).where(EvidenceGap.evidence_package_id == package.id))
    )
    diagnostics = opportunity_diagnostics(session, tenant_id, site_id)
    evaluation = next(
        (item for item in diagnostics["items"] if item["evidence_package_id"] == str(package.id)),
        None,
    )
    return {
        "id": str(package.id),
        "resource_type": "evidence_package",
        "label": entity.display_name,
        "description": f"Governed {package.classification.casefold().replace('_', ' ')} evidence for {entity.display_name}.",
        "why_it_matters": "Evidence packages combine source observations into the governed input used by opportunity detectors.",
        "summary": {
            "entity_type": entity.entity_type.value,
            "canonical_key": entity.canonical_key,
            "classification": package.classification,
            "sufficiency": package.sufficiency.value,
            "contract": contract.contract_key,
            "period_start": package.period_start.isoformat(),
            "period_end": package.period_end.isoformat(),
        },
        "quality": [row_data(item) for item in dimensions],
        "evidence": [row_data(item) for item in items],
        "gaps": [{**row_data(item), "href": f"/evidence/gaps/{item.id}"} for item in gaps],
        "opportunity_evaluation": evaluation,
        "relationships": {
            "market": f"/markets/{package.market_definition_id}"
            if package.market_definition_id
            else None,
            "demand_signal_id": encoded(package.demand_signal_id),
        },
        "rights": {"usability": package.rights_usability.value},
        "provenance": {
            "quality_run_id": str(package.quality_run_id),
            "method_version": package.method_version,
            "technical_id": str(package.id),
            "created_at": encoded(package.created_at),
        },
        "limitations": package.limitations_json,
    }


def evidence_gap_detail(
    session: Session, gap_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    row = session.execute(
        select(EvidenceGap, EvidencePackage, AnalyticalEntity)
        .join(EvidencePackage, EvidencePackage.id == EvidenceGap.evidence_package_id)
        .join(AnalyticalEntity, AnalyticalEntity.id == EvidencePackage.analytical_entity_id)
        .where(
            EvidenceGap.id == gap_id,
            EvidencePackage.tenant_id == tenant_id,
            EvidencePackage.site_id == site_id,
        )
    ).one_or_none()
    if not row:
        raise ApiError(404, "EVIDENCE_GAP_NOT_FOUND", "Evidence gap not found in site scope.")
    gap, package, entity = row
    return {
        "id": str(gap.id),
        "resource_type": "evidence_gap",
        "label": f"{gap.gap_type.replace('_', ' ').title()} · {entity.display_name}",
        "description": gap.description,
        "status": "RESOLVED" if gap.resolved_at else "OPEN",
        "urgency": gap.urgency.value,
        "desired_capability": gap.desired_evidence_capability,
        "collection_target_id": encoded(gap.collection_target_id),
        "relationships": {
            "evidence_package": f"/evidence/{package.id}",
            "collection_target": f"/collection/{gap.collection_target_id}"
            if gap.collection_target_id
            else None,
        },
        "provenance": gap.provenance_metadata,
        "technical_id": str(gap.id),
    }


def collection_inventory(
    session: Session,
    tenant_id: uuid.UUID,
    site_id: uuid.UUID,
    *,
    page: int,
    limit: int,
    search: Optional[str] = None,
    target_type: Optional[str] = None,
    status: Optional[str] = None,
    sort: str = "updated",
    order: str = "desc",
) -> dict[str, Any]:
    filters: list[Any] = [
        CollectionTarget.tenant_id == tenant_id,
        CollectionTarget.site_id == site_id,
    ]
    if search:
        filters.append(
            or_(
                CollectionTarget.display_value.ilike(f"%{search}%"),
                CollectionTarget.normalized_identity.ilike(f"%{search}%"),
            )
        )
    if target_type:
        filters.append(CollectionTarget.target_type == target_type)
    if status:
        filters.append(CollectionTarget.status == status)
    total = session.scalar(select(func.count()).select_from(CollectionTarget).where(*filters)) or 0
    sort_columns = {
        "name": CollectionTarget.display_value,
        "updated": CollectionTarget.updated_at,
        "status": CollectionTarget.status,
        "type": CollectionTarget.target_type,
    }
    column = sort_columns.get(sort, CollectionTarget.updated_at)
    ordering = desc(column) if order == "desc" else asc(column)
    targets = list(
        session.scalars(
            select(CollectionTarget)
            .where(*filters)
            .order_by(ordering, CollectionTarget.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
    )
    decisions = {}
    for target in targets:
        decisions[target.id] = session.scalar(
            select(CollectionPlanningDecision)
            .where(CollectionPlanningDecision.target_id == target.id)
            .order_by(CollectionPlanningDecision.evaluated_at.desc())
            .limit(1)
        )
    items = []
    for target in targets:
        decision = decisions[target.id]
        items.append(
            {
                "id": str(target.id),
                "label": target.display_value,
                "normalized_identity": target.normalized_identity,
                "type": target.target_type.value,
                "status": target.status.value,
                "status_explanation": COLLECTION_STATUS_HELP[target.status.value],
                "priority": decision.priority_tier.value if decision else "NOT_EVALUATED",
                "priority_score": encoded(decision.priority_score) if decision else None,
                "blocker": decision.primary_blocker.value if decision else "UNKNOWN",
                "cadence": decision.effective_cadence.value if decision else None,
                "updated_at": encoded(target.updated_at),
                "href": f"/collection/{target.id}",
            }
        )
    counts = {
        f"{kind.value}:{state.value}": count
        for kind, state, count in session.execute(
            select(CollectionTarget.target_type, CollectionTarget.status, func.count())
            .where(CollectionTarget.tenant_id == tenant_id, CollectionTarget.site_id == site_id)
            .group_by(CollectionTarget.target_type, CollectionTarget.status)
        )
    }
    return {
        **_page(items, page, limit, total),
        "counts": counts,
        "status_help": COLLECTION_STATUS_HELP,
    }


def collection_detail(
    session: Session, target_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    target = session.scalar(
        select(CollectionTarget).where(
            CollectionTarget.id == target_id,
            CollectionTarget.tenant_id == tenant_id,
            CollectionTarget.site_id == site_id,
        )
    )
    if not target:
        raise ApiError(
            404, "COLLECTION_TARGET_NOT_FOUND", "Collection target not found in site scope."
        )
    decision = session.scalar(
        select(CollectionPlanningDecision)
        .where(CollectionPlanningDecision.target_id == target.id)
        .order_by(CollectionPlanningDecision.evaluated_at.desc())
        .limit(1)
    )
    evidence = list(
        session.scalars(
            select(CollectionTargetEvidence)
            .where(CollectionTargetEvidence.target_id == target.id)
            .order_by(CollectionTargetEvidence.evidence_at.desc())
            .limit(100)
        )
    )
    plan = []
    if decision:
        plan = list(
            session.execute(
                select(CollectionPlanItem, CollectorCapability)
                .join(
                    CollectorCapability,
                    CollectorCapability.id == CollectionPlanItem.collector_capability_id,
                )
                .where(CollectionPlanItem.decision_id == decision.id)
            ).all()
        )
    signals = list(
        session.scalars(
            select(DemandSignal)
            .where(DemandSignal.collection_target_id == target.id)
            .order_by(DemandSignal.window_end.desc())
            .limit(50)
        )
    )
    gaps = list(
        session.scalars(select(EvidenceGap).where(EvidenceGap.collection_target_id == target.id))
    )
    return {
        "id": str(target.id),
        "resource_type": "collection_target",
        "label": target.display_value,
        "description": f"{target.target_type.value.title()} target in the governed collection-planning inventory.",
        "identity": row_data(target),
        "status": {
            "value": target.status.value,
            "explanation": COLLECTION_STATUS_HELP[target.status.value],
        },
        "decision": row_data(decision) if decision else None,
        "discovery_evidence": [row_data(item) for item in evidence],
        "collection_plan": [
            {
                **row_data(item),
                "collector": capability.capability_key,
                "evidence_product": capability.evidence_product,
            }
            for item, capability in plan
        ],
        "demand_signals": [row_data(item) for item in signals],
        "evidence_gaps": [{**row_data(item), "href": f"/evidence/gaps/{item.id}"} for item in gaps],
        "relationships": {"market": f"/markets/{target.market_definition_id}"},
        "technical_id": str(target.id),
    }


def market_detail(
    session: Session, market_id: uuid.UUID, tenant_id: uuid.UUID, site_id: uuid.UUID
) -> dict[str, Any]:
    market = session.scalar(
        select(MarketDefinition).where(
            MarketDefinition.id == market_id,
            MarketDefinition.tenant_id == tenant_id,
            MarketDefinition.site_id == site_id,
        )
    )
    if not market:
        raise ApiError(404, "MARKET_NOT_FOUND", "Market not found in site scope.")
    members = list(
        session.scalars(
            select(MarketDefinitionMember)
            .where(MarketDefinitionMember.market_definition_id == market.id)
            .order_by(MarketDefinitionMember.rank_order)
        )
    )
    observations = list(
        session.scalars(
            select(MarketObservation)
            .where(
                MarketObservation.market_definition_id == market.id,
                MarketObservation.effective_end.is_(None),
            )
            .order_by(MarketObservation.observed_at.desc())
        )
    )
    observation_ids = [item.id for item in observations]
    participants = (
        list(
            session.scalars(
                select(MarketParticipantObservation)
                .where(MarketParticipantObservation.market_observation_id.in_(observation_ids))
                .order_by(MarketParticipantObservation.visibility_share.desc())
                .limit(100)
            )
        )
        if observation_ids
        else []
    )
    metrics = (
        list(
            session.scalars(
                select(MarketMetricObservation).where(
                    MarketMetricObservation.market_observation_id.in_(observation_ids)
                )
            )
        )
        if observation_ids
        else []
    )
    target_counts = {
        kind.value: count
        for kind, count in session.execute(
            select(CollectionTarget.target_type, func.count())
            .where(CollectionTarget.market_definition_id == market.id)
            .group_by(CollectionTarget.target_type)
        )
    }
    return {
        "id": str(market.id),
        "resource_type": "market",
        "label": market.name,
        "description": market.description
        or "The observable competitive and search universe used to evaluate demand, visibility, collection coverage, evidence, and opportunities.",
        "why_it_matters": "The market bounds what GIS compares; it prevents isolated observations from being interpreted without competitive context.",
        "definition": row_data(market),
        "members": [row_data(item) for item in members],
        "observations": [row_data(item) for item in observations],
        "participants": [row_data(item) for item in participants],
        "metrics": [row_data(item) for item in metrics],
        "target_counts": target_counts,
        "coverage_note": f"{len(participants)} participant rows across {len(observations)} current market observation(s). Result-row volume is not longitudinal coverage.",
        "relationships": {
            "collection": f"/collection?market={market.id}",
            "evidence": f"/evidence?market={market.id}",
            "opportunities": f"/opportunities?market={market.id}",
        },
        "technical_id": str(market.id),
    }
